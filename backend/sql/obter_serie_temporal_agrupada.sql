-- RPC para agregar série temporal no banco e evitar paginação de linhas cruas no backend.
-- Ajuste o nome da tabela em FROM caso seu dataset principal não seja `public.distribuicao`.

create or replace function public.obter_serie_temporal_agrupada(
    _ano integer default null,
    _mes integer default null,
    _uf text default null,
    _fabricante text default null
)
returns table (
    ano integer,
    mes integer,
    doses bigint
)
language sql
stable
as $$
    select
        d.ano,
        d.mes,
        sum(d.qtde)::bigint as doses
    from public.distribuicao d
    where (_ano is null or d.ano = _ano)
      and (_mes is null or d.mes = _mes)
      and (_uf is null or d.tx_sigla ilike '%' || _uf || '%')
      and (_fabricante is null or d.tx_insumo ilike '%' || _fabricante || '%')
    group by d.ano, d.mes
    order by d.ano, d.mes;
$$;
