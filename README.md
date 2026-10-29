# Document Tree Summarizer

A resumable, bottom-up document summarizer using text extraction and local-AI generated summaries. Python runs with `uv`, Apache Tika and OCRmyPDF run with **Docker Compose**, and **Ollama runs natively** for best performance. The result is a self-contained expandable/collapsible HTML report.

## Setup (Mac)

1. Install [uv](https://docs.astral.sh/uv/), [Docker Desktop](https://www.docker.com/products/docker-desktop/), and [Ollama](https://ollama.com/download/mac/).
2. Start Docker Desktop and download the OCR and Tika images: `docker compose pull`. No local OCRmyPDF, Tesseract, or Tika installation is required.
3. Download local models: `ollama pull qwen3:14b`, `ollama pull qwen3:32b`, and `ollama pull qwen2.5vl:3b` (or the model set in `extraction.image.model`).
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
  --database "$HOME/local-ai-results/cache.sqlite3" \
  --sample 50
```

Open the resulting `summary.html` in a browser. No server is needed. Expand or collapse any directory or file, or use the Expand all / Collapse all buttons.

Use `uv run summarizer --help` for additional flags. `--sample` accepts an integer from 0 to 100 and defaults to 100. It randomly selects that percentage of supported files in each directory for extraction and document summarization; directories still receive every immediate filename and file type, plus summaries of sampled files and child directories. Use `--sample 0` for directory summaries based on that inventory and child directory summaries. Use `--model qwen3:14b --directory-model qwen3:32b` to override the YAML models.

Progress is logged to stderr by default with timestamps: the current directory and file, hashing and extraction stages, extractor attempts, cache hits, model name, chunk counts, reduction rounds, and completion times. Operations taking longer than 60 seconds print a "Still working" message with the active path and elapsed time, repeated every 60 seconds. Ollama retries are logged, and the final message includes processed file, failure, and completed directory counts. Add `--verbose` for debug logging. To keep a log while watching progress, append `2>&1 | tee summarizer.log` to your command.

## How the hierarchy works

At the default sample level of 100, every supported file is extracted and summarized. Each directory is summarized from **only its immediate file inventory (filenames and types, with summaries for sampled files) and immediate subdirectory summaries**, not from all descendant source text. Directories are processed bottom-up. For long inputs, chunk summaries are recursively reduced so the model receives bounded text.

Each directory entry in the HTML report also shows a programmatically calculated count and total size for all regular files beneath it, plus the earliest and latest file modification dates in UTC. Each summarized file shows its size and modification date. Sizes use bytes below 1 KB and scale through KB, MB, GB, and TB using 1,000 bytes per unit. Symlinks and the generated report are excluded; files without a configured extraction route still count toward directory totals.

## Configuration

Edit `config.yaml`:

- `extraction.routes`: select `builtin`, `tika`, or `docling` per extension.
- `extraction.docling.enabled`: enabled in the supplied config, with routes for PDF, Office Open XML, OpenDocument, HTML, Markdown, CSV, images, and other [supported Docling formats](https://docling-project.github.io/docling/usage/supported_formats/). PDF/image processing may download models on first use. Docling uses its own OCR pipeline; `extraction.ocr` settings apply only to the built-in PDF extractor. Generic JSON/XML and plain text use `builtin`; legacy Office and RTF use `tika`.
- Images are first characterized by the configured local vision model (`extraction.image.model`, default `qwen2.5vl:3b`). Ordinary photographs and other non-document images are summarized from the visual description. Images classified as scanned documents are then extracted through their configured route (Docling by default, with Tika fallback). The supplied full Tika image includes Tesseract OCR for image formats. Multi-page TIFF/GIF characterization samples up to `extraction.image.max_pages` pages, resized to `extraction.image.max_dimension` pixels on the longest edge; document extraction still receives the original file. Ollama HTTP errors include the server response to aid troubleshooting.
- `extraction.fallback`: optional ordered list of alternative extractors.
- `extraction.ocr.backend`: `docker` (default) runs the `ocrmypdf` Compose service once per PDF needing OCR, then removes the container. PDFs stream through stdin/stdout, so no document directories need to be mounted. The `ocr` profile keeps this job service out of `docker compose up -d`.
- `extraction.ocr.compose_file`: optional path to the Compose file; defaults to this repository's `compose.yaml`, independent of your working directory. Set an absolute path if installing the Python package outside this checkout.
- `extraction.ocr.mode`: `auto`, `off`, or `always` for built-in PDF extraction. OCRmyPDF is called on PDFs that contain pages with little text.
- `extraction.ocr.language`: Tesseract language codes such as `eng` or `eng+fra`. Additional languages must be installed in a custom OCR image; see the [OCRmyPDF Docker documentation](https://ocrmypdf.readthedocs.io/en/latest/docker.html). To use a local installation instead, set `backend: native` and install `ocrmypdf` (on macOS: `brew install ocrmypdf`, optionally `brew install tesseract-lang`).
- `summarization.document_model`: model for files.
- `summarization.directory_model`: model for directory synthesis.
- `summarization.chunk_chars`, `group_chars`: upper bounds for input chunking; tune based on actual context usage.

Tika is served at `http://127.0.0.1:9998`; Ollama at `http://127.0.0.1:11434`. No cloud AI APIs are used.

## Caching

The SQLite database caches extraction, document summary and directory summary stages separately. Cache keys incorporate source contents, configuration, prompts and model names. Restarting an interrupted run reuses successful cached results. Failed files appear in the report and are excluded from parent syntheses.

Inspect the `cache_entries` view to see each key's absolute source path, filename (or directory name), model, and summary part (chunk or reduction group):

```sql
SELECT stage, path, filename, model, part, key
FROM cache_entries
ORDER BY path, stage, part;
```

Extraction rows have a NULL model because extraction does not use a summarization model. Shared content can produce multiple source rows for the same key. Existing databases are upgraded automatically without invalidating results; older entries have NULL metadata until reused by a run. Original paths cannot be recovered from hashes alone.

## Output

The output HTML renders summary Markdown as headings, lists, emphasis, tables, links, and code blocks. Filenames, warnings, and raw HTML in summaries are escaped; unsafe link schemes and embedded images are disabled. The report has no external assets or JavaScript dependencies. 

## Safety and privacy

Do not expose the Tika service to the network; do not process untrusted documents without appropriate sandboxing. For strict offline processing, pre-download the Compose images, Ollama models and any Docling model dependencies, then test disconnected from the network. Avoid syncing the input/output/cache directories to cloud storage.

## Limitations

- OCR and layout extraction can be inaccurate; validate summaries against source documents.
- DOCX embedded images/textboxes and complicated layouts may need Docling or Tika.
- Tika may not preserve PDF page citations. Use the built-in PDF route when page labels matter.
- The pipeline is sequential by design (one Ollama request at a time). It does not yet include a parallel OCR worker pool or a progress dashboard.
- A single huge model summary may be truncated during reduction to stay within the configured input budget. For high-stakes work, audit the result and increase budgets as appropriate.
- A directory with failed descendants may still have a successful parent summary; the report marks failures and warnings at the affected level.
- Pin container image digests and commit `uv.lock` and `.python-version` for reproducible deployments. After syncing dependencies, use `uv sync --locked --python 3.12` (add `--extra docling` when needed) to install without updating the lockfile.
