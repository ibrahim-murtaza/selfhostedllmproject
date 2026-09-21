"""
Docling CPU-only conversion test. Mirrors how the gateway service will call
Docling: PDF bytes in, markdown out, no GPU.

Run (from any folder, pass the PDF path):
    python docling_cpu_test.py test_document.pdf
"""

import os
import sys
import time

# Hide GPUs from torch before anything imports it. Belt and braces on top of
# the AcceleratorOptions below.
os.environ["CUDA_VISIBLE_DEVICES"] = ""

from io import BytesIO

from docling.datamodel.base_models import DocumentStream, InputFormat
from docling.datamodel.pipeline_options import (
    AcceleratorDevice,
    AcceleratorOptions,
    PdfPipelineOptions,
)
from docling.document_converter import DocumentConverter, PdfFormatOption

MARKERS = ["ALPHA-7421", "OMEGA-9036", "Engineering", "Replacement Value"]

if len(sys.argv) != 2:
    sys.exit("usage: python docling_cpu_test.py <file.pdf>")

path = sys.argv[1]
with open(path, "rb") as f:
    pdf_bytes = f.read()

pipeline_options = PdfPipelineOptions()
pipeline_options.accelerator_options = AcceleratorOptions(
    device=AcceleratorDevice.CPU
)

t0 = time.monotonic()
converter = DocumentConverter(
    format_options={
        InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
    }
)
t_init = time.monotonic() - t0

t1 = time.monotonic()
result = converter.convert(DocumentStream(name=os.path.basename(path), stream=BytesIO(pdf_bytes)))
markdown = result.document.export_to_markdown()
t_convert = time.monotonic() - t1

print(f"converter init : {t_init:.2f}s")
print(f"convert        : {t_convert:.2f}s")
print(f"markdown chars : {len(markdown)}")
print()
for m in MARKERS:
    print(f"{'FOUND  ' if m in markdown else 'MISSING'} {m}")
print()
print("---- markdown (first 1500 chars) ----")
print(markdown[:1500])