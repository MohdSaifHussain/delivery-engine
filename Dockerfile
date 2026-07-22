# Delivery Engine — production-ready container
# Mirrors the CI workflow exactly: Python 3.12 + Node 24 + analystkit from GitHub
# Build: docker build -t delivery-engine .
# Test:  docker run --rm delivery-engine python -m pytest -q

FROM python:3.12-slim

# ── System dependencies ────────────────────────────────────────────────────────
# git: analystkit installs from GitHub via pip
# curl + gnupg: needed to add the NodeSource repo
# build-essential: native Python extension compilation (duckdb etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    gnupg \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# ── Node.js 24 (matches CI: actions/setup-node@v6 node-version: "24") ─────────
RUN curl -fsSL https://deb.nodesource.com/setup_24.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# ── Working directory ──────────────────────────────────────────────────────────
WORKDIR /app

# ── Copy repo (respects .dockerignore — excludes data/, output/, .git etc.) ───
COPY . .

# ── Node packages (matches CI: npm install pptxgenjs docx) ────────────────────
RUN npm install pptxgenjs docx

# ── Python dependencies (matches CI install order exactly) ────────────────────
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir \
        "git+https://github.com/MohdSaifHussain/analystkit.git" \
    && pip install --no-cache-dir -e ./analystkit-mcp \
    && pip install --no-cache-dir -e ./opskit-mcp \
    && pip install --no-cache-dir -e ".[dev,ml,docs,stats]"

# ── Document verification tools (matches CI) ──────────────────────────────────
RUN pip install --no-cache-dir "markitdown[pptx]"

# ── DuckDB extensions (matches CI: pre-install so network failures are loud) ──
RUN python -c "\
import duckdb; \
c = duckdb.connect(); \
c.execute('INSTALL excel'); \
c.execute('INSTALL sqlite'); \
print('duckdb extensions ready')"

# ── Default command: run the full test suite ───────────────────────────────────
CMD ["python", "-m", "pytest", "-q"]
