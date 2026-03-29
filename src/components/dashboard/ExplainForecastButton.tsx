import React from "react";
import { Dialog, DialogTrigger, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogClose } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Info } from "lucide-react";

const ExplainForecastButton = () => {
  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">
          <Info className="mr-2 h-4 w-4" /> Como Calculamos a Previsão?
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Como a Projeção (2025) é Calculada?</DialogTitle>
          <DialogDescription>
            Para criar a Projeção de Distribuição para 2025, o sistema utiliza um método estatístico avançado, como se estivesse traçando uma linha de tendência:
            <ul className="mt-2 ml-4 list-disc">
              <li>
                <strong>Olhamos o Histórico Completo:</strong> Primeiro, somamos o Total de Doses Distribuídas em cada ano, desde 2020 até 2024.
              </li>
              <li>
                <strong>Encontramos a Tendência:</strong> Usamos uma técnica chamada Análise de Tendência (Regressão Linear) para entender se a distribuição anual está crescendo, caindo ou permanecendo estável ao longo desses anos.
              </li>
              <li>
                <strong>Projetamos o Valor:</strong> Essa tendência é então usada para extrapolar o valor para 2025. O resultado é uma estimativa de quanto o total distribuído em 2025 será, mantendo o mesmo padrão de crescimento/queda do período recente.
              </li>
            </ul>
            <div className="mt-3 text-sm">
              Nota: Ao contrário da simples 'média' que diluiria valores importantes, este método garante que o alto volume dos anos recentes seja o principal fator na sua projeção, resultando em uma estimativa de Total Anual mais realista.
            </div>
          </DialogDescription>
        </DialogHeader>
        <div className="mt-4 text-right">
          <DialogClose asChild>
            <Button variant="default" size="sm">Fechar</Button>
          </DialogClose>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default ExplainForecastButton;
