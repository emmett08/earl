PYTHON ?= python3
.PHONY: all reproduce check figures pdf submission clean
all: pdf

reproduce:
	$(PYTHON) analysis/reproduce.py
	$(PYTHON) analysis/check_listing.py --write

check:
	$(PYTHON) analysis/reproduce.py --check
	$(PYTHON) analysis/check_listing.py

figures: check
	$(PYTHON) analysis/render_figures.py

pdf: figures
	latexmk -pdf -interaction=nonstopmode -halt-on-error manuscript.tex

submission: pdf
	$(PYTHON) analysis/make_submission.py

clean:
	latexmk -c manuscript.tex
