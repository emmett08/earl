PYTHON ?= python3
export SOURCE_DATE_EPOCH := 1790366400
export FORCE_SOURCE_DATE := 1
.PHONY: all reproduce figures check clean
all: figures
	latexmk -pdf -halt-on-error -interaction=nonstopmode -outdir=build manuscript.tex
	cp build/manuscript.pdf manuscript.pdf
reproduce:
	$(PYTHON) analysis/reproduce.py
figures: reproduce
	$(PYTHON) analysis/make_figures.py
	$(PYTHON) analysis/render_figures.py
check: all
	$(PYTHON) analysis/check_paper.py
clean:
	rm -rf build
