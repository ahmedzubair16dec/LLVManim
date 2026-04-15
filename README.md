# LLVManim Paper

> *Presentable Debugging with LLVManim* — an IEEE-format conference paper describing the LLVManim code visualization tool.

## Clone the Repository

```bash
git clone git@github.com:BenHoule/LLVManim-Paper.git
cd LLVManim-Paper
```

## Install LaTeX

### Ubuntu / Debian

```bash
sudo apt-get update
sudo apt-get install -y \
    texlive-latex-base \
    texlive-latex-recommended \
    texlive-latex-extra \
    texlive-fonts-recommended \
    texlive-fonts-extra \
    texlive-bibtex-extra \
    texlive-science \
    texlive-pictures \
    python3-pygments
```

| apt package                    | Provides                                                    |
| ------------------------------ | ----------------------------------------------------------- |
| `texlive-latex-base`           | Core LaTeX (`pdflatex`)                                     |
| `texlive-latex-recommended`    | `fontenc`, `graphicx`, `hyperref`, `bookmark`, etc.         |
| `texlive-latex-extra`          | `minted`, `etoolbox`, `float`, `multicol`, `placeins`, etc. |
| `texlive-fonts-recommended`    | Standard fonts                                              |
| `texlive-fonts-extra`          | Extra fonts used by IEEEtran                                |
| `texlive-bibtex-extra`         | `IEEEtran.bst` BibTeX style                                |
| `texlive-science`              | `amsmath`, `amssymb`, `algorithmic`                         |
| `texlive-pictures`             | TikZ / PGF (used by `pgfornament`)                          |
| `python3-pygments`             | Pygments for `minted` syntax highlighting                   |

### macOS (MacTeX)

Install [MacTeX](https://tug.org/mactex/) (full distribution), then ensure Pygments is available:

```bash
pip3 install Pygments
```

### Verify installation

```bash
pdflatex --version
bibtex --version
pygmentize -V
```

## Compile the Paper

### Quick build (no bibliography)

```bash
bash build.sh
```

This runs `pdflatex -shell-escape` once, which is enough if you only need to check formatting. References will show as **[?]**.

### Full build (with bibliography)

```bash
pdflatex -shell-escape -interaction=nonstopmode proposal.tex
bibtex proposal
pdflatex -shell-escape -interaction=nonstopmode proposal.tex
pdflatex -shell-escape -interaction=nonstopmode proposal.tex
```

Run `pdflatex` twice after `bibtex` so that cross-references and citations resolve correctly.

The output is **`proposal.pdf`**.

### VS Code (LaTeX Workshop)

If you use VS Code with the [LaTeX Workshop](https://marketplace.visualstudio.com/items?itemName=James-Yu.latex-workshop) extension, the workspace already includes a `.vscode/settings.json` with two recipes:

- **pdflatex × 2** — quick compilation without bibliography.
- **pdflatex → bibtex → pdflatex × 2** — full build with bibliography.

## (Optional) Regenerate Figures

Some figures are generated from draw.io, PlantUML, and SVG sources. To regenerate them:

```bash
# Install additional dependencies
sudo apt-get install -y xvfb plantuml
pip3 install cairosvg

# draw.io CLI must be on $PATH (install from https://github.com/jgraph/drawio-desktop/releases)

python3 generate_images.py
```

This is only needed if you modify the source diagrams; pre-built PDFs are already committed.
