PYTHON ?= python3
.PHONY: all reproduce reproduce-plots check check-supplemental figures pdf submission clean
all: pdf

reproduce:
	$(PYTHON) analysis/reproduce.py
	$(PYTHON) analysis/check_listing.py --write

reproduce-plots:
	$(PYTHON) analysis/check_plot_reproduction.py

check:
	$(PYTHON) analysis/reproduce.py --check
	$(PYTHON) analysis/check_listing.py
	$(PYTHON) analysis/check_figures.py
	$(PYTHON) analysis/check_editorial.py
	$(PYTHON) analysis/check_supplemental_measurement.py

check-supplemental:
	$(PYTHON) analysis/check_supplemental_measurement.py

figures: check
	@true

pdf: figures
	latexmk -pdf -interaction=nonstopmode -halt-on-error manuscript.tex

submission: pdf
	$(PYTHON) analysis/make_submission.py

clean:
	latexmk -c manuscript.tex
