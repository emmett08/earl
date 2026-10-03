.PHONY: pdf source clean

source:
	python3 reproduction/typeset.py

pdf: source
	latexmk -pdf -interaction=nonstopmode -halt-on-error engineering-argumentation.tex

clean:
	latexmk -c engineering-argumentation.tex
