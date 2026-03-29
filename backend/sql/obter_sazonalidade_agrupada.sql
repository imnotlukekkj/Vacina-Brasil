create or replace function public.obter_sazonalidade_agrupada(
    _ano integer default null,
    _uf text default null,
    _fabricante text default null
)
returns table (
    mes integer,
    qtde bigint
)
language sql
stable
as $$
    select
        d.mes,
        sum(d.qtde)::bigint as qtde
    from public.distribuicao d
    where (_ano is null or d.ano = _ano)
      and (_uf is null or d.tx_sigla ilike '%' || _uf || '%')
      and (_fabricante is null or d.tx_insumo ilike '%' || _fabricante || '%')
    group by d.mes
    order by d.mes asc;
$$;
