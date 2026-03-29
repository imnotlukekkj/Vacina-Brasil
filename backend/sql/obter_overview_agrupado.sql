create or replace function public.obter_overview_agrupado(
    _ano integer default null,
    _mes integer default null,
    _uf text default null,
    _fabricante text default null
)
returns table (
    total_doses bigint
)
language sql
stable
as $$
    select
        sum(d.qtde)::bigint as total_doses
    from public.distribuicao d
    where (_ano is null or d.ano = _ano)
      and (_mes is null or d.mes = _mes)
      and (_uf is null or d.tx_sigla ilike '%' || _uf || '%')
      and (_fabricante is null or d.tx_insumo ilike '%' || _fabricante || '%');
$$;
