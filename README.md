# cloudflare-api-schemas
Cloudflare API JSON Schemas (+extraction tool)

**Why**: It's 2022, devs want to use API schemas to generate modern API wrappers (strictly typed, for example). Cloudflare doesn't provide access to their API schemas for unknown reasons, even their official Python wrapper uses beautifulsoup to parse their own docs.

**What**: This repository provides schemas and a tool to extract them (`scripts/extractor.py`, just run `make` to generate fresh schemas). I don't guarantee that extracted schemas are identical to the original (hidden), but it's enough to build projects (wrappers, pentest, and so on) on top of it.

**How**: Obviously CF uses some toolchain [1] to generate their docs from internally available API schemas. Part of this job is reflected in the minified js app bundle used by the official documentation website. I use `esprima` js parser to convert js objects containing meaningful information to Python dicts, to serialize them back to JSON schemas.

[1] https://blog.cloudflare.com/cloudflares-json-powered-documentation-generator/