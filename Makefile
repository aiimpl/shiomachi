PORT ?= 8795
PY ?= .venv/bin/python
BLENDER ?= blender
B = $(BLENDER) -b --factory-startup --python-exit-code 1
D = web/data
C = build/check

.PHONY: serve setup bake ship port islands preview frames audio video check clean

# Open http://127.0.0.1:8795/ after this
serve:
	python3 -m http.server $(PORT) --bind 127.0.0.1 --directory web

setup:
	python3 -m venv .venv
	.venv/bin/pip install -r requirements.txt

# Rebuild all baked data: the ship and the harbour kit in Blender (textures baked with Cycles), the islands with numpy
bake: ship port islands

ship:
	mkdir -p $(C)
	$(B) -P bake/ship.py -- bake $(D) $(C) 4096
	cwebp -quiet -q 90 $(D)/ship_base.png -o $(D)/ship_base.webp
	cwebp -quiet -q 95 $(D)/ship_orm.png -o $(D)/ship_orm.webp
	rm -f $(D)/ship_base.png $(D)/ship_orm.png

port:
	$(B) -P bake/port.py -- $(D) 4096
	cwebp -quiet -q 90 $(D)/port_base.png -o $(D)/port_base.webp
	cwebp -quiet -q 95 $(D)/port_orm.png -o $(D)/port_orm.webp
	rm -f $(D)/port_base.png $(D)/port_orm.png

islands:
	mkdir -p $(C)
	$(PY) bake/islands.py $(D) $(C)

# Check renders of the ship alone (Cycles), for comparing with the reference photographs
preview:
	$(B) -P bake/ship.py -- preview build/preview

# The film (film.js): 780 frames at 2x, about 15 min on an Apple M Mac; resumes if interrupted
frames:
	$(PY) tools/render.py build/frames 0 -1 30

audio: frames
	$(PY) tools/audio.py build/frames build/shiomachi.wav 30

video: audio
	sh tools/encode.sh build/frames build/shiomachi.wav build/shiomachi.mp4

# Syntax check of the Python side
check:
	$(PY) -m pyflakes bake tools

clean:
	rm -rf build
