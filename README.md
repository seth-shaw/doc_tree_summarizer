# Document Tree Summarizer

A resumable, bottom-up document summarizer using text extraction and local-AI generated summaries. Python runs with `uv`, Apache Tika and OCRmyPDF run with **Docker Compose**, and **Ollama runs natively** for best performance. The result is a self-contained expandable/collapsible HTML report.

## Setup (Mac)

1. Install [uv](https://docs.astral.sh/uv/), [Docker Desktop](https://www.docker.com/products/docker-desktop/), and [Ollama](https://ollama.com/download/mac/).
2. Start Docker Desktop and download the OCR and Tika images: `docker compose pull`. No local OCRmyPDF, Tesseract, or Tika installation is required.
3. Download local models: `ollama pull qwen3:14b` and `ollama pull qwen3:32b`.
4. In this directory, install and pin Python 3.12, then sync dependencies:

   ```bash
   uv python install 3.12
   uv python pin 3.12
   uv sync --python 3.12
   ```

   The supplied `config.yaml` enables Docling for supported document and image formats, so use `uv sync --python 3.12 --extra docling` instead of the last command with that configuration. For an installation without Docling, set `extraction.docling.enabled: false` and change its routes to `builtin` or `tika` as appropriate.

5. Start OCR & Tika Services: `docker compose up -d`. The Tika port is accessible only on your Mac's loopback interface. Tika is optional for the built-in formats, but required for routed formats such as `.pptx` and `.eml`.
6. Verify services: `curl http://127.0.0.1:9998/version` and `ollama list`.

## Run

```bash
uv run summarizer "$HOME/Documents/MyCollection" \
  --config config.yaml \
  --output "$HOME/local-ai-results/summary.html" \
  --database "$HOME/local-ai-results/cache.sqlite3"
```

Open the resulting `summary.html` in a browser. No server is needed. Expand or collapse any directory or file, or use the Expand all / Collapse all buttons.

Use `uv run summarizer --help` for additional flags. Use `--model qwen3:14b --directory-model qwen3:32b` to override the YAML models.

## How the hierarchy works

Every supported file is extracted and summarized. Each directory is summarized from **only its immediate file summaries and immediate subdirectory summaries**, not from all descendant source text. Directories are processed bottom-up. For long inputs, chunk summaries are recursively reduced so the model receives bounded text.

## Configuration

Edit `config.yaml`:

- `extraction.routes`: select `builtin`, `tika`, or `docling` per extension.
- `extraction.docling.enabled`: enabled in the supplied config, with routes for PDF, Office Open XML, OpenDocument, HTML, Markdown, CSV, images, and other [supported Docling formats](https://docling-project.github.io/docling/usage/supported_formats/). PDF/image processing may download models on first use. Docling uses its own OCR pipeline; `extraction.ocr` settings apply only to the built-in PDF extractor. Generic JSON/XML and plain text use `builtin`; legacy Office and RTF use `tika`.
- `extraction.fallback`: optional ordered list of alternative extractors.
- `extraction.ocr.backend`: `docker` (default) runs the `ocrmypdf` Compose service once per PDF needing OCR, then removes the container. PDFs stream through stdin/stdout, so no document directories need to be mounted. The `ocr` profile keeps this job service out of `docker compose up -d`.
- `extraction.ocr.compose_file`: optional path to the Compose file; defaults to this repository's `compose.yaml`, independent of your working directory. Set an absolute path if installing the Python package outside this checkout.
- `extraction.ocr.mode`: `auto`, `off`, or `always` for built-in PDF extraction. OCRmyPDF is called on PDFs that contain pages with little text.
- `extraction.ocr.language`: Tesseract language codes such as `eng` or `eng+fra`. Additional languages must be installed in a custom OCR image; see the [OCRmyPDF Docker documentation](https://ocrmypdf.readthedocs.io/en/latest/docker.html). To use a local installation instead, set `backend: native` and install `ocrmypdf` (on macOS: `brew install ocrmypdf`, optionally `brew install tesseract-lang`).
- `summarization.document_model`: model for files.
- `summarization.directory_model`: model for directory synthesis.
- `summarization.chunk_chars`, `group_chars`: upper bounds for input chunking; tune based on actual context usage.

Tika is served at `http://127.0.0.1:9998`; Ollama at `http://127.0.0.1:11434`. No cloud AI APIs are used.

## Caching and privacy

The SQLite database caches extraction, document summary and directory summary stages separately. Cache keys incorporate source contents, configuration, prompts and model names. Restarting an interrupted run reuses successful cached results. Failed files appear in the report and are excluded from parent syntheses.

The output HTML renders summary Markdown as headings, lists, emphasis, tables, links, and code blocks. Filenames, warnings, and raw HTML in summaries are escaped; unsafe link schemes and embedded images are disabled. The report has no external assets or JavaScript dependencies. Do not expose the Tika service to the network; do not process untrusted documents without appropriate sandboxing. For strict offline processing, pre-download the Compose images, Ollama models and any Docling model dependencies, then test disconnected from the network. Avoid syncing the input/output/cache directories to cloud storage.

## Limitations

- OCR and layout extraction can be inaccurate; validate summaries against source documents.
- DOCX embedded images/textboxes and complicated layouts may need Docling or Tika.
- Tika may not preserve PDF page citations. Use the built-in PDF route when page labels matter.
- The pipeline is sequential by design (one Ollama request at a time). It does not yet include a parallel OCR worker pool or a progress dashboard.
- A single huge model summary may be truncated during reduction to stay within the configured input budget. For high-stakes work, audit the result and increase budgets as appropriate.
- A directory with failed descendants may still have a successful parent summary; the report marks failures and warnings at the affected level.
- Pin container image digests and commit `uv.lock` and `.python-version` for reproducible deployments. After syncing dependencies, use `uv sync --locked --python 3.12` (add `--extra docling` when needed) to install without updating the lockfile.
