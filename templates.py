"""
templates.py — Templates pré-definidos de carrossel e dataclasses.
"""

from dataclasses import dataclass, field


# ─── Dataclasses ─────────────────────────────────────────────────────────────

@dataclass
class SlideEstrutura:
    slide: int
    tipo: str          # Capa, Segunda Capa, Entrega, Ponte, Prova, CTA
    texto: str
    usa_foto_real: bool = False
    tipo_foto: str | None = None  # "fachada" | "laboratorio" | "alunos" | None


@dataclass
class CarouselIdea:
    titulo: str
    eixo: str          # Didático | Comportamental | Diagnóstico
    tema: str
    publico_alvo: str
    palavras_chave_seo: list = field(default_factory=list)
    cta: str = ""
    slides_sugeridos: list = field(default_factory=list)
    kpi_alvo: str = ""
    justificativa: str = ""
    persona_alvo: str = ""
    tipo_hook: str = ""
    score: int = 0
    score_justificativa: str = ""

    def to_dict(self) -> dict:
        return {
            "titulo": self.titulo,
            "eixo": self.eixo,
            "tema": self.tema,
            "publico_alvo": self.publico_alvo,
            "palavras_chave_seo": self.palavras_chave_seo,
            "cta": self.cta,
            "slides_sugeridos": self.slides_sugeridos,
            "kpi_alvo": self.kpi_alvo,
            "justificativa": self.justificativa,
            "persona_alvo": self.persona_alvo,
            "tipo_hook": self.tipo_hook,
            "score": self.score,
            "score_justificativa": self.score_justificativa,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CarouselIdea":
        return cls(
            titulo=d.get("titulo", ""),
            eixo=d.get("eixo", "Didático"),
            tema=d.get("tema", ""),
            publico_alvo=d.get("publico_alvo", ""),
            palavras_chave_seo=d.get("palavras_chave_seo", []),
            cta=d.get("cta", ""),
            slides_sugeridos=d.get("slides_sugeridos", []),
            kpi_alvo=d.get("kpi_alvo", ""),
            justificativa=d.get("justificativa", ""),
            persona_alvo=d.get("persona_alvo", ""),
            tipo_hook=d.get("tipo_hook", ""),
            score=d.get("score", 0),
            score_justificativa=d.get("score_justificativa", ""),
        )



@dataclass
class MetricaPost:
    data: str
    titulo: str
    alcance: int
    salvamentos: int
    envios_dm: int
    nao_seguidores: int
    comentarios: int
    leads_whatsapp: int
    taxa_salvamentos: float = 0.0
    taxa_envios: float = 0.0
    taxa_nao_seguidores: float = 0.0

    def calcular_taxas(self) -> None:
        if self.alcance > 0:
            self.taxa_salvamentos = round(self.salvamentos / self.alcance * 100, 1)
            self.taxa_envios = round(self.envios_dm / self.alcance * 100, 1)
            self.taxa_nao_seguidores = round(self.nao_seguidores / self.alcance * 100, 1)

    def to_dict(self) -> dict:
        return {
            "data": self.data,
            "titulo": self.titulo,
            "alcance": self.alcance,
            "salvamentos": self.salvamentos,
            "taxa_salvamentos": self.taxa_salvamentos,
            "envios_dm": self.envios_dm,
            "taxa_envios": self.taxa_envios,
            "nao_seguidores": self.nao_seguidores,
            "taxa_nao_seguidores": self.taxa_nao_seguidores,
            "comentarios": self.comentarios,
            "leads_whatsapp": self.leads_whatsapp,
        }


# ─── Templates Pré-definidos ─────────────────────────────────────────────────

TEMPLATES: dict[str, dict] = {
    "desconstrucao_didatica": {
        "nome": "Desconstrução Didática",
        "eixo": "Didático",
        "icone": "📚",
        "descricao": "Descomplica um problema típico de prova. Maximiza salvamentos.",
        "kpi_alvo": "Salvamentos ≥ 4%",
        "cta_padrao": "DESAFIO",
        "estrutura": [
            SlideEstrutura(1, "Capa",         "Enunciado de problema típico cobrado no Ensino Fundamental"),
            SlideEstrutura(2, "Segunda Capa", "Por que a leitura apressada induz ao raciocínio errado"),
            SlideEstrutura(3, "Entrega",      "Método passo a passo — etapa 1"),
            SlideEstrutura(4, "Entrega",      "Método passo a passo — etapa 2"),
            SlideEstrutura(5, "Entrega",      "Método passo a passo — etapa 3"),
            SlideEstrutura(6, "Ponte",        "Como o ensino individualizado resolve a lacuna", True, "alunos"),
            SlideEstrutura(7, "Prova",        "Foto real da fachada — Rua Coelho Lisboa, 783",  True, "fachada"),
            SlideEstrutura(8, "CTA",          "Salve este post! Comente DESAFIO ou chame no WhatsApp (11) 94475-0009"),
        ],
    },
    "alivio_pressao": {
        "nome": "Alívio da Pressão Acadêmica",
        "eixo": "Comportamental",
        "icone": "🧠",
        "descricao": "Alivia a ansiedade dos pais. Maximiza envios por DM.",
        "kpi_alvo": "Envios DM ≥ 2,5%",
        "cta_padrao": "FOCO",
        "estrutura": [
            SlideEstrutura(1, "Capa",         "A rotina de cobrança e o peso das notas"),
            SlideEstrutura(2, "Segunda Capa", "O que acontece neurologicamente com a ansiedade"),
            SlideEstrutura(3, "Entrega",      "Atitude prática 1 dos pais em casa"),
            SlideEstrutura(4, "Entrega",      "Atitude prática 2 dos pais em casa"),
            SlideEstrutura(5, "Entrega",      "Atitude prática 3 dos pais em casa"),
            SlideEstrutura(6, "Ponte",        "Diferença entre estudo passivo e ativo",          True, "alunos"),
            SlideEstrutura(7, "Prova",        "Foto real da fachada — portão branco, Tatuapé",   True, "fachada"),
            SlideEstrutura(8, "CTA",          "Envie para outro pai/mãe ou fale no WhatsApp: (11) 94475-0009"),
        ],
    },
    "conversao_diagnostica": {
        "nome": "Conversão Diagnóstica (Telas vs. Lógica)",
        "eixo": "Diagnóstico",
        "icone": "💻",
        "descricao": "Converte pais preocupados com telas em leads. Maximiza WhatsApp.",
        "kpi_alvo": "Leads WhatsApp 15-25/semana",
        "cta_padrao": "AULA",
        "estrutura": [
            SlideEstrutura(1, "Capa",         "O dilema tempo de tela vs. futuro acadêmico"),
            SlideEstrutura(2, "Segunda Capa", "Consumo passivo vs. criação ativa"),
            SlideEstrutura(3, "Entrega",      "Como programação melhora concentração"),
            SlideEstrutura(4, "Entrega",      "Benefícios da lógica para raciocínio matemático"),
            SlideEstrutura(5, "Entrega",      "Atividades práticas do laboratório",                True, "laboratorio"),
            SlideEstrutura(6, "Ponte",        "Depoimento ou registro do laboratório",             True, "laboratorio"),
            SlideEstrutura(7, "Prova",        "Foto real da fachada — Unidade Tatuapé",            True, "fachada"),
            SlideEstrutura(8, "CTA",          "Comente AULA ou agende sua visita no WhatsApp (11) 94475-0009"),
        ],
    },
}


def get_template_estrutura_dict(template_key: str) -> list[dict]:
    """Retorna a estrutura do template como lista de dicts (serializável)."""
    template = TEMPLATES.get(template_key)
    if not template:
        return []
    return [
        {
            "slide": s.slide,
            "tipo": s.tipo,
            "texto": s.texto,
            "usa_foto_real": s.usa_foto_real,
            "tipo_foto": s.tipo_foto,
        }
        for s in template["estrutura"]
    ]


def eixo_para_template(eixo: str) -> str:
    """Mapeia o eixo estratégico para a chave do template correspondente."""
    mapa = {
        "Didático": "desconstrucao_didatica",
        "Comportamental": "alivio_pressao",
        "Diagnóstico": "conversao_diagnostica",
    }
    return mapa.get(eixo, "desconstrucao_didatica")
