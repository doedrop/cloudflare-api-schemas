PYTHON = python

build:
	$(PYTHON) scripts/extractor.py

clean:
	rm -rf schemas