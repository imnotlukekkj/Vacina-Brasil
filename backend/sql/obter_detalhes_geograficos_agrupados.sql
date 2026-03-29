create or replace function public.obter_detalhes_geograficos_agrupados(
    _ano integer default null,
    _mes integer default null,
    _fabricante text default null
)
returns table (
    tx_sigla text,
    tx_insumo text,
    qtde bigint
)
language sql
stable
as $$
    with agregados as (
        select
            d.tx_sigla,
            d.tx_insumo,
            sum(d.qtde)::bigint as qtde
        from public.distribuicao d
        where (_ano is null or d.ano = _ano)
          and (_mes is null or d.mes = _mes)
          and (_fabricante is null or d.tx_insumo ilike '%' || _fabricante || '%')
        group by d.tx_sigla, d.tx_insumo
    ),
    ranqueados as (
        select
            a.tx_sigla,
            a.tx_insumo,
            a.qtde,
            row_number() over (
                partition by a.tx_sigla
                order by a.qtde desc, a.tx_insumo asc
            ) as rn
        from agregados a
    )
    select
        r.tx_sigla,
        r.tx_insumo,
        r.qtde
    from ranqueados r
    where r.rn = 1
    order by r.tx_sigla asc;
$$;
