import os
import re
import json
import shutil
import requests

from typing import Optional, Dict
from pathlib import Path
from datetime import datetime
from urllib.parse import urljoin

from esprima.visitor import NodeVisitor, Visited
from esprima.parser import Parser

from lxml import etree

__all__ = [
    'extract_schemas', 'CLOUDFLARE_DOCS_URL', 'CLOUDFLARE_SCHEMAS_URL',
]

CLOUDFLARE_DOCS_URL = os.environ.get('NX_CLOUDFLARE_DOCS_URL', 'https://api.cloudflare.com/')
CLOUDFLARE_SCHEMAS_URL = os.environ.get('NX_CLOUDFLARE_SCHEMAS_URL', f'{CLOUDFLARE_DOCS_URL}schemas/v4/')

# This regexp is pretty fragile and definitely a subject to get broken in the future, but we cannot afford
# parsing the entire app using esprima, so this is kinda a tradeoff. TODO: Find better way to process app.js
RE_APP_SECTION = re.compile(r'function\([a-z],\s*[a-z]\)\s*\{\s*[a-z]\.exports\s*=\s*\{')


def _fetch_text(
    url: str, *,
    cache_path: Optional[str] = None,
    invalidate: bool = False
) -> str:
    if cache_path and not invalidate:
        if os.path.exists(cache_path):
            with open(cache_path) as cache_file:
                return cache_file.read()
    plain_text = requests.get(url).text
    if cache_path:
        with open(cache_path, 'w') as cache_file:
            cache_file.write(plain_text)
    return plain_text


def _process_docs(text: str, *, base_url: str) -> Dict:
    tree = etree.fromstring(text, parser=etree.HTMLParser(huge_tree=True, remove_comments=True))
    return {
        'sections': tree.xpath('//article[contains(@class, "api-section")]/header/h2/text()'),
        'app_url': urljoin(base_url, tree.xpath('//script[contains(@src, "apidocs-static/app-")]/@src')[0]),
    }


class _PyVisitor(NodeVisitor):

    def visit_Literal(self, obj):
        return obj.value

    def visit_Identifier(self, obj):
        return obj.name

    def visit_Property(self, obj):
        return self.visit(obj.key), self.visit(obj.value)

    def visit_ArrayExpression(self, obj):
        return [self.visit(item) for item in obj.elements]

    def visit_ObjectExpression(self, obj):
        return dict([self.visit(prop) for prop in obj.properties])

    def visit_Object(self, obj):
        raise Exception(f'Unhandled object type "{obj.type}"')

    def visit_UnaryExpression(self, obj):
        match obj.operator:
            case '!':
                return not obj.argument.value
            case '-':
                return -obj.argument.value
            case _:
                raise Exception(f'Unhandled unary operator "{obj.operator}" ({obj})')

    def visit_dict(self, obj):
        for field, value in list(obj.items()):
            yield value
        yield Visited(obj)


def _process_app(code: str) -> Dict:
    result = {}
    visitor, obj_pos = _PyVisitor(), 0
    while section := RE_APP_SECTION.search(code, pos=obj_pos):
        obj_pos = section.span()[1] - 1
        py_obj = visitor.visit(Parser(code[obj_pos:]).parseObjectInitializer())
        if py_obj and not py_obj.get('cfHidden', False):
            py_id = (
                py_obj['id']
                .replace(CLOUDFLARE_SCHEMAS_URL, '')
                .replace('.json', '')
                .replace('/', '.')
                .replace('-', '_')
            )
            result[py_id] = py_obj
    return result


def extract_schemas(
    *,
    output_path: Optional[Path | str] = None,
    verify: bool = True,
    append_meta: bool = True,
    remove_existing: bool = False,
    app_url: Optional[str] = None,
    base_url: Optional[str] = None,
) -> Dict:
    docs_info = {}
    if not app_url:
        base_url = base_url or CLOUDFLARE_DOCS_URL
        docs_info = _process_docs(_fetch_text(base_url), base_url=base_url)
        app_url = docs_info['app_url']

    api_schemas = _process_app(_fetch_text(app_url))
    if verify and docs_info:
        # TODO: Do we have additional ways to verify the integrity?
        assert len(docs_info['sections']) == len(api_schemas)

    meta = {
        # TODO: Does the original app bundle have some version? Would be great to find it ;)
        '_generated_on': datetime.utcnow().isoformat(),
        '_generated_from': app_url,
    } if append_meta else {}

    if output_path:
        output_path = Path(output_path)
        if remove_existing and output_path.exists():
            shutil.rmtree(output_path)

        for _, schema in api_schemas.items():
            file_path = output_path / schema['id'].replace(CLOUDFLARE_SCHEMAS_URL, '')
            os.makedirs(file_path.parent, exist_ok=True)
            with open(file_path, 'w') as json_file:
                json.dump({
                    **schema,
                    **meta,
                }, json_file, indent=4)

    api_schemas.update(meta)
    return api_schemas


if __name__ == '__main__':
    all_schemas = extract_schemas(output_path='../schemas/', remove_existing=True)
    with open('../schemas/schemas.json', 'w') as schemas_file:
        json.dump(all_schemas, schemas_file, indent=4)
