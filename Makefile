# =============================================================================
# Shortcuts for running the pipeline on your own Mac.
#
# The same commands GitHub Actions runs - just typed by hand. Nothing here is
# Mac-specific; it works on Linux too.
#
# Type `make` on its own to see this list.
# =============================================================================

.PHONY: help setup demo topics choose write build render clean check

help:
	@echo ""
	@echo "  make setup            Install everything (run once)"
	@echo "  make demo             Render a 14-second test video, no API keys needed"
	@echo "  make check            Check that every module imports and the config is valid"
	@echo ""
	@echo "  make topics           Propose 10 topics                    (Gate 1)"
	@echo "  make choose PICK=3    Record which topic you chose"
	@echo "  make write            Research + write the script          (Gate 2)"
	@echo "  make build            Narrate, build visuals, render, done"
	@echo ""
	@echo "  make render           Re-run just the render step"
	@echo "  make clean            Delete build output (keeps your runs)"
	@echo ""

setup:
	python3 -m venv venv
	./venv/bin/pip install --upgrade pip
	./venv/bin/pip install -r requirements.txt
	cd remotion && npm install
	@echo ""
	@echo "Done. Now:"
	@echo "  1. cp .env.example .env"
	@echo "  2. Fill in the keys in .env"
	@echo "  3. source venv/bin/activate"
	@echo "  4. make demo"

demo:
	python tools/make_demo.py
	cd remotion && npx remotion render MainVideo out/demo.mp4 --props=demo-props.json
	@echo "Demo video: remotion/out/demo.mp4"

check:
	python -c "import pipeline.run; print('all modules import cleanly')"
	python -c "from pipeline.common import load_config, load_brand; load_config(); load_brand(); print('config files are valid')"

topics:
	python -m pipeline.run topics

choose:
	python -m pipeline.run choose --run latest --pick $(PICK)

write:
	python -m pipeline.run write --run latest

build:
	python -m pipeline.run build --run latest

render:
	python -m pipeline.run stage render --run latest

clean:
	rm -rf remotion/out remotion/public/current
	@echo "Cleaned. Your runs/ folder is untouched."
