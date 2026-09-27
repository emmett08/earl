PYTHON ?= python3
export SOURCE_DATE_EPOCH := 1790467200
export FORCE_SOURCE_DATE := 1
.PHONY: all check reproduce clean
all:
	latexmk -pdf -halt-on-error -interaction=nonstopmode -outdir=build manuscript.tex
	cp build/manuscript.pdf manuscript.pdf
reproduce:
	@test -n "$(ARCHIVE)" || (echo 'Pass ARCHIVE=/path/to/api-experiment-36275725154-1.zip' >&2; exit 2)
	$(PYTHON) analysis/analyse_run.py "$(ARCHIVE)"
	$(PYTHON) analysis/make_figures.py --zip "$(ARCHIVE)"
check: all
	$(PYTHON) analysis/check_paper.py
clean:
	rm -rf build
