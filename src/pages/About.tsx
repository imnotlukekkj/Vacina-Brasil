import { motion } from "framer-motion";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Activity, ArrowLeft, BookOpen, Target, Users, Code } from "lucide-react";

const About = () => {
  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b bg-card sticky top-0 z-50 backdrop-blur-sm">
        <div className="container mx-auto px-4 py-4 flex justify-between items-center">
          <Link to="/" className="flex items-center gap-2">
            <Activity className="h-8 w-8 text-primary" />
            <h1 className="text-xl font-bold text-foreground">Vacina Brasil</h1>
          </Link>
          <Link to="/dashboard">
            <Button variant="default">Acessar Dashboard</Button>
          </Link>
        </div>
      </header>

      {/* Content */}
      <div className="container mx-auto px-4 py-12 max-w-4xl">
        <Link to="/">
          <Button variant="ghost" className="mb-8">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Voltar
          </Button>
        </Link>

        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="space-y-8">
          {/* Título */}
          <div>
            <h1 className="text-4xl font-bold text-foreground mb-4">Sobre o Projeto</h1>
            <p className="text-xl text-muted-foreground">Dashboard Nacional de Distribuição de Vacinas</p>
          </div>

          {/* Objetivo */}
          <Card>
            <CardHeader>
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-primary/10 rounded-lg flex items-center justify-center">
                  <Target className="h-5 w-5 text-primary" />
                </div>
                <CardTitle>Objetivo</CardTitle>
              </div>
            </CardHeader>
            <CardContent>
              <p className="text-muted-foreground leading-relaxed">
                Este projeto acadêmico tem como objetivo fornecer uma interface moderna e intuitiva para
                visualização e análise de dados públicos sobre a distribuição de vacinas em
                território nacional. Através de gráficos interativos, mapas e indicadores-chave, busca-se
                facilitar o acompanhamento da campanha de vacinação e promover a transparência dos dados
                oficiais do Ministério da Saúde.
              </p>
            </CardContent>
          </Card>

          {/* Metodologia */}
          <Card>
            <CardHeader>
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-secondary/10 rounded-lg flex items-center justify-center">
                  <BookOpen className="h-5 w-5 text-secondary" />
                </div>
                <CardTitle>Metodologia</CardTitle>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <h4 className="font-semibold text-foreground mb-2">Fonte de Dados</h4>
                <p className="text-muted-foreground">
                  Os dados utilizados são provenientes de bases públicas do Ministério da Saúde,
                  processados através de uma API FastAPI que disponibiliza endpoints REST para
                  consulta de indicadores, séries temporais e rankings por UF.
                </p>
              </div>
              <div>
                <h4 className="font-semibold text-foreground mb-2">Stack Tecnológica</h4>
                <ul className="list-disc list-inside text-muted-foreground space-y-1">
                  <li>Frontend: React + TypeScript + Vite</li>
                  <li>Backend: FastAPI (Python)</li>
                  <li>Visualização: Recharts e React Simple Maps</li>
                  <li>UI: TailwindCSS + shadcn/ui</li>
                  <li>Estado: Zustand</li>
                  <li>Animações: Framer Motion</li>
                </ul>
              </div>
              <div>
                <h4 className="font-semibold text-foreground mb-2">Funcionalidades</h4>
                <ul className="list-disc list-inside text-muted-foreground space-y-1">
                  <li>Filtros dinâmicos por ano, mês, UF e vacinas</li>
                  <li>KPIs em tempo real</li>
                  <li>Série temporal com visualização gráfica</li>
                  <li>Mapa interativo do Brasil com dados por UF</li>
                  <li>Design responsivo e acessível</li>
                </ul>
              </div>
            </CardContent>
          </Card>

          {/* Autores */}
          <Card>
            <CardHeader className="flex flex-col items-start">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-primary/10 rounded-lg flex items-center justify-center">
                  <Users className="h-5 w-5 text-primary" />
                </div>
                <CardTitle>Idealizadores do Projeto</CardTitle>
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-1 text-muted-foreground">
                <div className="font-semibold text-foreground">Luis Felipe Leandro Gomes</div>
                <div className="font-semibold text-foreground">Yasmin Douahy Rebelo</div>
                <div className="font-semibold text-foreground">Jamilly Douahy Rebelo</div>
                <div className="font-semibold text-foreground">João Felipe Da Graça Almeida</div>
                <div className="font-semibold text-foreground">Marcos Vinícius Mendes Arruda</div>
              </div>
            </CardContent>
          </Card>

          {/* Desenvolvedores */}
          <Card>
            <CardHeader className="flex flex-col items-start">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-primary/10 rounded-lg flex items-center justify-center">
                  <Code className="h-5 w-5 text-primary" />
                </div>
                <CardTitle>Desenvolvedores</CardTitle>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              <div>
                <p className="font-semibold text-foreground">Luis Felipe Leandro Gomes</p>
                <p className="text-muted-foreground text-sm">Front-end, Back-end, integrações e responsável pelo deploy da aplicação.</p>
              </div>
              <div>
                <p className="font-semibold text-foreground">Yasmin Douahy Rebelo</p>
                <p className="text-muted-foreground text-sm">Banco de dados e hospedagem do banco na nuvem.</p>
              </div>
            </CardContent>
          </Card>

          {/* Links úteis */}
          <Card>
            <CardHeader className="flex flex-col items-start">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-secondary/10 rounded-lg flex items-center justify-center">
                  <BookOpen className="h-5 w-5 text-secondary" />
                </div>
                <CardTitle>Contexto Acadêmico</CardTitle>
              </div>
            </CardHeader>
            <CardContent className="space-y-2">
              <p><span className="font-semibold text-foreground">Curso:</span> <span className="text-muted-foreground">Análise e Desenvolvimento de Sistemas e Ciência da Computação</span></p>
              <p className="text-muted-foreground"><span className="font-semibold text-foreground">Disciplina:</span> Tópicos de Big Data em Python</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Links e Recursos</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <a href="https://opendatasus.saude.gov.br/" target="_blank" rel="noopener noreferrer" className="block text-primary hover:text-primary/80 transition-colors">→ OpenDataSUS - Portal de Dados Abertos da Saúde</a>
              <a href="https://www.gov.br/saude/pt-br" target="_blank" rel="noopener noreferrer" className="block text-primary hover:text-primary/80 transition-colors">→ Ministério da Saúde</a>
              <a href="https://github.com/imnotlukekkj/Vacina-Brasil" target="_blank" rel="noopener noreferrer" className="block text-primary hover:text-primary/80 transition-colors">→ Repositório do Projeto (GitHub)</a>
            </CardContent>
          </Card>
        </motion.div>
      </div>
    </div>
  );
};

export default About;
