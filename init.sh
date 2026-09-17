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

# 1. Verifica/install uv
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

# 3. Ativa virtualenv
source .venv/bin/activate

# 4. Instala dependencies (usa lockfile)
if [ ! -f ".venv/lib/python*/site-packages/streamlit/__init__.py" ]; then
    echo -e "${YELLOW}⏳ Instalando dependências...${NC}"
    uv pip sync uv.lock
fi

# 5. Copia .env.example se não existir
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⏳ Configurando .env...${NC}"
    cp .env.example .env
    echo -e "${YELLOW}⚠️ Edite .env e configure a API_KEY_GEMINI${NC}"
fi

# 6. Inicia o app
echo -e "${GREEN}✅ Ambiente pronto! Iniciando app...${NC}"
streamlit run app.py --server.headless true
