# Test images

`compliant.png`, `missing_mrp.png`, `missing_address.png`, `tiny_mrp_print.png`
and `unreadable.png` are synthetic labels from `tools/make_test_labels.py`. They
prove the pipeline runs; they say nothing about real-world accuracy.

**Drop real product photos in this folder.** Clean renders and actual packaging
are different problems — gloss, curvature, low-contrast print, and bilingual
text are what will break the regexes in `rules.py`, and none of them appear in a
synthetic PNG.

To see what OCR actually reads from a photo, before any rule logic touches it:

    python ocr.py test-images/your-photo.jpg
