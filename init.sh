#!/bin/bash
set -e

# Color output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "${GREEN}===================================${NC}"
echo "${GREEN}  Motor de Carrosséis — Setup Rápido  ${NC}"
echo "${GREEN}===================================${NC}"
echo

# 1. Verifica/instala uv
if ! command -v uv &> /dev/null; then
    echo -e "${YELLOW}⏳ Instalando uv...${NC}"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

# 2. Cria virtualenv se necessário
if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}⏳ Criando virtualenv...${NC}"
    uv venv .venv
fi

# 3. Instala dependencies (usa venv existente)
if [ ! -f ".venv/lib/python*/site-packages/streamlit/__init__.py" ]; then
    echo -e "${YELLOW}⏳ Instalando dependências...${NC}"
    uv pip install --python .venv/bin/python -e .
fi

# 4. Copia .env.example se não existir
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⏳ Configurando .env...${NC}"
    cp .env.example .env
    echo -e "${YELLOW}⚠️ Edite .env e configure a API_KEY_GEMINI${NC}"
fi

# 5. Inicia o app
echo -e "${GREEN}✅ Ambiente pronto! Iniciando app...${NC}"
.venv/bin/python -m streamlit run app.py --server.headless true
