create or replace function public.obter_ranking_ufs_agrupado(
    _ano integer default null,
    _mes integer default null,
    _uf text default null,
    _fabricante text default null
)
returns table (
    uf text,
    doses bigint
)
language sql
stable
as $$
    select
        d.tx_sigla as uf,
        sum(d.qtde)::bigint as doses
    from public.distribuicao d
    where (_ano is null or d.ano = _ano)
      and (_mes is null or d.mes = _mes)
      and (_uf is null or d.tx_sigla ilike '%' || _uf || '%')
      and (_fabricante is null or d.tx_insumo ilike '%' || _fabricante || '%')
    group by d.tx_sigla
    order by sum(d.qtde) desc;
$$;
