from typing import List, Optional, Any
from pydantic import BaseModel


class ComparisonDataPoint(BaseModel):
    ano: int
    quantidade: Optional[float]
    tipo: str


class ComparisonResponse(BaseModel):
    insumo: str
    projecao_unidade: str
    dados_comparacao: List[ComparisonDataPoint]
    # optional debug fields
    rpc_raw_soma: Optional[Any] = None
    rpc_raw_previsao: Optional[Any] = None
