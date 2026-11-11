# Guia: como tirar o máximo do Claude Code (para quem não é programador)

O segredo não é saber programar, e sim atuar como **gerente de produto e arquiteto**:
guiar o Claude com clareza, contexto e validação constante. O maior risco é pedir
coisas grandes demais de uma vez e se perder nos erros.

---

## 1. Preparação: memória e checkpoints

### CLAUDE.md (a "bíblia" do projeto)
Rode `/init` na pasta do projeto. Ele cria o `CLAUDE.md`, lido pelo Claude em toda
sessão. Registre ali: objetivo do sistema, tecnologias usadas e as regras abaixo.

```markdown
## Regras de trabalho
- Explique o que fez em linguagem simples, sem jargão.
- Antes de mudanças grandes, apresente o plano e espere minha aprovação.
- Nunca apague funcionalidades existentes sem perguntar.
- Faça uma coisa por vez; ao terminar, diga como EU testo (passo a passo).
- Rode os testes antes de dizer que terminou. Se falharem, mostre o erro.
- Faça commit a cada funcionalidade que funciona, com mensagem em português.
- Segredos (senhas, chaves de API) sempre no .env, nunca no código.
- Ao adicionar uma biblioteca, explique por que e confira se ainda é mantida.
```

### Git desde o primeiro minuto
O Git é o "salvar jogo". Peça: *"Inicie um repositório Git e faça commit sempre que
terminarmos uma funcionalidade que funciona."* Se algo quebrar, peça para voltar ao
último ponto seguro.

### Segredos
Peça logo no início: *"use um arquivo `.env` para chaves e coloque o `.env` no
`.gitignore`"*. Nunca envie senhas para o GitHub.

---

## 2. Etapas de desenvolvimento

1. **Planejamento e especificação** – descreva a ideia, peça que o Claude faça
   perguntas e salve um `SPEC.md`/`PLANO.md` com telas, regras e fluxo do usuário.
2. **Tecnologias simples e populares** – menos erros difíceis (ex.: Python, FastAPI,
   SQLite, Next.js, Tailwind, Supabase).
3. **Construção em blocos (MVP)** – visual básico → lógica → banco de dados e login.
4. **Testes e refinamento** – após cada bloco, rode localmente e teste. Só avance
   quando o bloco atual funcionar.

### Critério de aceite (o método mais útil para não programadores)
Para cada funcionalidade, escreva **antes** como saberá que está pronta:

> "Pronto = escolho 01/11 08:00 a 07/11 18:00, clico em Filtrar, e só aparecem
> conversas desse período. O contador no topo bate com a lista."

O Claude transforma isso num teste automático, e você tem como validar a entrega
sem ler código.

---

## 3. Comandos e recursos

| Recurso | Para que serve |
|---|---|
| **Modo Planejamento** (`Shift+Tab` no terminal) | O Claude só lê e planeja, sem alterar arquivos, até você aprovar. |
| **`/clear`** | Apaga o histórico da conversa (arquivos intactos). Use ao mudar de tarefa. |
| **`/compact`** | Resume a conversa sem apagá-la. Use quando a tarefa ainda não acabou mas a conversa está longa. |
| **`Esc` `Esc` ou `/rewind`** | Volta código e conversa a um ponto anterior. Mais rápido que o Git para desfazer o último passo. |
| **Colar prints de tela** | Mostrar a tela quebrada costuma funcionar melhor que descrevê-la. |
| **`/code-review` e `/security-review`** | O Claude revisa o próprio código antes do commit. Essencial se o app guarda dados de clientes. |
| **Subagentes** | Pesquisa paralela: *"use um subagente para comparar 3 bibliotecas"*, sem encher a conversa principal. |
| **MCP / conectores** | Ligam o Claude a ferramentas externas (GitHub, bancos de dados etc.). |

---

## 4. Como conversar com o Claude

- **Descreva sintomas, não suposições**: *"Quando clico em Salvar, a tela fica branca"*.
- **Cole o erro inteiro** (texto vermelho do terminal ou navegador).
- **Peça testes**: *"Crie um teste que garante que o cálculo X funciona e rode agora."*
- **Peça explicações visuais**: *"Desenhe um fluxograma em texto de como os dados fluem."*
- **Divida tarefas complexas**: em vez de "sistema de pagamentos completo", peça
  1) tela de checkout, 2) integração em modo de teste, 3) tela de confirmação.

---

## 5. Aplicação: gerenciador de WhatsApp Business

### Objetivo
App leve e portátil (pasta Python, sem instalação) que conecta ao WhatsApp via QR Code,
lê e salva as conversas na inicialização, classifica-as, mostra as últimas mensagens dos
grupos e permite filtrar por período (data/hora de início e fim). Base: o bot
"Agente ZAP" existente.

### Decisão crítica antes do código: como conectar

| | **Não oficial (QR Code)** | **Oficial (WhatsApp Business Platform / Cloud API da Meta)** |
|---|---|---|
| Exemplos | neonize (Python), whatsapp-web.js, Baileys, WPPConnect, Evolution API | API da Meta |
| Conexão | Ler o QR Code, como no WhatsApp Web | Cadastro na Meta, número verificado, webhooks |
| Ler conversas antigas | Sim, limitado ao que o WhatsApp sincroniza ao conectar | Em geral só mensagens novas. No modo "coexistência" com o app Business, a Meta permite importar parte do histórico (confira as regras atuais) |
| Risco | **Viola os termos do WhatsApp; o número pode ser banido** | Nenhum, é o caminho permitido |
| Custo | Grátis | Cobrança por conversa/modelo de mensagem |

Recomendações:
- Teste com um **número secundário**.
- Mantenha a conexão num **módulo isolado**, para trocar pela API oficial depois sem
  refazer o resto.

### Arquitetura sugerida

```
[WhatsApp] ⇄ Conector (QR)  →  Banco SQLite  →  Classificador  →  Painel Web local
            (módulo isolado)   (1 arquivo)     (regras + IA)     (abre no navegador)
```

- **Python** em pasta portátil (distribuição com PyInstaller ou "Python embeddable").
- **SQLite**: um arquivo, sem servidor.
- **Painel**: FastAPI + HTML simples, ou Streamlit.
- **Classificação**: primeiro regras simples (palavras-chave, cliente novo/antigo, sem
  resposta há X horas); depois IA (ex.: API do Claude com modelo barato) para intenção:
  "orçamento", "reclamação", "suporte".

### Fases (cada uma termina com um commit funcionando)

1. **Conexão** – gerar QR, conectar, mostrar "conectado" com o nome do número.
2. **Captura** – salvar no SQLite as mensagens sincronizadas e as novas.
   *Aceite: total de conversas no banco bate com o do celular.*
3. **Filtro de período** – data/hora de início e fim.
   *Aceite: "últimos 7 dias" retorna só esse período.* O filtro só alcança
   mensagens já sincronizadas.
4. **Painel** – lista de conversas, busca e visualização de cada conversa.
5. **Classificação** – regras, depois IA, com etiquetas editáveis.
6. **Grupos** – últimas mensagens de cada grupo.
7. **Empacotamento** – pasta portátil e um "LEIA-ME" de uso.
8. **Integração com o Agente ZAP** – reaproveitar ou unificar a lógica.

### Usar um projeto do GitHub como base
Antes de adotar algo do tópico `whatsapp-api-python`, peça:

> "Avalie estes 3 repositórios: data do último commit, issues abertas sobre
> banimento/desconexão, licença (MIT/Apache permitem uso comercial; GPL tem
> exigências) e se suporta histórico e grupos. Recomende um."

Bibliotecas de WhatsApp quebram com frequência quando o WhatsApp muda; ser mantida
ativamente vale mais que ter muitas estrelas.

---

## 6. Primeiro prompt (para quando anexar o projeto)

```
Anexei meu bot "Agente ZAP" (Python, roda em pasta portátil). Não sou programador
experiente; atue como meu arquiteto técnico.

Objetivo: evoluí-lo para um gerenciador leve de WhatsApp Business que conecta via
QR Code, lê e salva as conversas, classifica-as e permite filtrar por período
(data/hora de início e fim), incluindo grupos.

Antes de qualquer código:
1. Leia o projeto e me explique, em linguagem simples, como ele funciona hoje.
2. Rode /init e crie o CLAUDE.md com as regras de trabalho do GUIA_CLAUDE_CODE.md.
3. Me faça até 5 perguntas sobre o que não ficou claro.
4. Compare 2-3 bibliotecas de conexão (incluindo riscos de banimento e a
   alternativa oficial da Meta) e recomende uma.
5. Crie um PLANO.md com fases pequenas, cada uma com critério de aceite.
Só comece a fase 1 depois da minha aprovação.
```
