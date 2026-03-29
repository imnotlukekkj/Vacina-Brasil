import { motion } from "framer-motion";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Activity, BarChart3, Map, Shield } from "lucide-react";
import ThemeToggle from "@/components/dashboard/ThemeToggle";

const Landing = () => {
  return (
    <div className="min-h-screen bg-gradient-to-br from-primary/5 via-background to-secondary/5">
      {/* Header */}
      <header className="border-b bg-card/50 backdrop-blur-sm sticky top-0 z-50">
        <div className="container mx-auto px-4 py-4 flex justify-between items-center">
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            className="flex items-center gap-2"
          >
            <Activity className="h-8 w-8 text-primary" />
            <h1 className="text-xl font-bold text-foreground">Vacina Brasil</h1>
          </motion.div>
          <nav className="flex gap-4 items-center">
            <Link to="/sobre" className="text-muted-foreground hover:text-foreground transition-colors">
              Sobre
            </Link>
            <ThemeToggle />
          </nav>
        </div>
      </header>

      {/* Hero Section */}
      <section className="container mx-auto px-4 py-20 text-center">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="max-w-4xl mx-auto"
        >
          <h2 className="text-5xl md:text-6xl font-bold text-foreground mb-6">
            Dashboard Nacional de
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary to-secondary">
              {" "}Distribuição de Vacinas
            </span>
          </h2>
          <p className="text-xl text-muted-foreground mb-8 max-w-2xl mx-auto">
            Visualize e analise dados oficiais de distribuição e aplicação de vacinas em todo o território nacional em tempo real.
          </p>
          <Link to="/dashboard">
            <Button size="lg" className="text-lg px-8 py-6 shadow-lg hover:shadow-xl transition-all">
              Acessar Dashboard
              <BarChart3 className="ml-2 h-5 w-5" />
            </Button>
          </Link>
        </motion.div>
      </section>

      {/* Features Section */}
      <section className="container mx-auto px-4 py-20">
        <div className="grid md:grid-cols-3 gap-8">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="bg-card rounded-xl p-8 shadow-lg hover:shadow-xl transition-all"
          >
            <div className="w-12 h-12 bg-primary/10 rounded-lg flex items-center justify-center mb-4">
              <BarChart3 className="h-6 w-6 text-primary" />
            </div>
            <h3 className="text-xl font-semibold mb-3 text-card-foreground">Análise em Tempo Real</h3>
            <p className="text-muted-foreground">
              Acompanhe KPIs atualizados de distribuição, aplicação e estoque de vacinas em todo o país.
            </p>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="bg-card rounded-xl p-8 shadow-lg hover:shadow-xl transition-all"
          >
            <div className="w-12 h-12 bg-secondary/10 rounded-lg flex items-center justify-center mb-4">
              <Map className="h-6 w-6 text-secondary" />
            </div>
            <h3 className="text-xl font-semibold mb-3 text-card-foreground">Mapa Interativo</h3>
            <p className="text-muted-foreground">
              Visualize a distribuição geográfica de vacinas por UF com cores e estatísticas detalhadas.
            </p>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
            className="bg-card rounded-xl p-8 shadow-lg hover:shadow-xl transition-all"
          >
            <div className="w-12 h-12 bg-primary/10 rounded-lg flex items-center justify-center mb-4">
              <Shield className="h-6 w-6 text-primary" />
            </div>
            <h3 className="text-xl font-semibold mb-3 text-card-foreground">Dados Oficiais</h3>
            <p className="text-muted-foreground">
              Informações baseadas em dados oficiais do Ministério da Saúde com total transparência.
            </p>
          </motion.div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t bg-card/50 backdrop-blur-sm py-8 mt-20">
        <div className="container mx-auto px-4 text-center text-muted-foreground">
          <p>© 2025 Dashboard Nacional de Distribuição de Vacinas - Projeto Acadêmico</p>
          <p className="mt-2 text-sm">
            Desenvolvido com dados públicos do Ministério da Saúde
          </p>
        </div>
      </footer>
    </div>
  );
};

export default Landing;
