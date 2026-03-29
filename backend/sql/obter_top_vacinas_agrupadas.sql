create or replace function public.obter_top_vacinas_agrupadas(
    _ano integer default null,
    _mes integer default null,
    _uf text default null,
    _fabricante text default null
)
returns table (
    tx_insumo text,
    qtde bigint
)
language sql
stable
as $$
    select
        d.tx_insumo,
        sum(d.qtde)::bigint as qtde
    from public.distribuicao d
    where (_ano is null or d.ano = _ano)
      and (_mes is null or d.mes = _mes)
      and (_uf is null or d.tx_sigla ilike '%' || _uf || '%')
      and (_fabricante is null or d.tx_insumo ilike '%' || _fabricante || '%')
    group by d.tx_insumo
    order by sum(d.qtde) desc, d.tx_insumo asc
    limit 5;
$$;
