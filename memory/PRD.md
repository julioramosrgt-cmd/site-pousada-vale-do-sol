# PRD - Sistema de Gestão de Pousada Vale do Sol

## Problema
Proprietário de pousada precisa de site público + sistema completo de gestão: quartos, calendário unificado, formulário público FNRH, sincronização iCal com Airbnb/Booking/TripLar, templates WhatsApp com PIX, módulo financeiro (receitas/despesas) e gestão de galeria/configurações.

## User Personas
- Anfitrião/Recepção (admin): gerencia tudo pelo painel.
- Hóspede (público): navega pelo site e envia pré-reserva via formulário FNRH (write-only).

## Arquitetura
- Backend FastAPI + MongoDB, JWT auth, RBAC (admin vs público), object storage (Emergent), icalendar, Stripe (sandbox claimable).
- Frontend React + Tailwind + shadcn/ui, react-router.
- Design: paleta terracotta + palm green + areia.
- Agendamentos: `.emergent/crons.yml` (plataforma dispara chamadas HTTP autenticadas por `WEBHOOK_CRON_SECRET`).

## Implementado
### 2026-02 — Base
- Auth JWT, site público, FNRH `/reservar`, painel admin completo (reservas, quartos, calendário, financeiro, iCal, WhatsApp templates, galeria), object storage, iCal auto-sync 15min, voucher PDF, QR code.

### 2026-02 — Motor de Precificação
- 10% sex/sáb, 2º adulto −10%, criança 0-3 (1ª grátis / demais 65%), pets 20.7/27.6/34.5%.
- Classificação automática de 156 raças + fallback manual.

### 2026-02 — Autocomplete + Feriados Nacionais
- Dropdown de raças com teclado.
- Feriados BR fixos + móveis (Páscoa Gregoriana) → sobretaxa 10% automática + badge "🎉 Nome".
- Endpoint `GET /api/public/holidays`.

### 2026-02 — Seção de Pagamento + Link Stripe + Cron (esta sessão)
- **Nav "Pagamento"** no header → âncora `#pagamento` com scroll suave.
- **Badges Visa/Mastercard/Elo** (SVG inline) na seção.
- **Stripe (sandbox claimable)**: `POST /api/reservations/{id}/payment-link` cria Checkout Session dinâmica em BRL. Webhook `POST /api/stripe/webhook` marca reserva como `paid` + `status=confirmed` idempotentemente. Admin tem botões "Gerar link" / "Copiar" / "Enviar por WhatsApp" por reserva. Coluna "Pagamento" mostra badge Pago/Aguardando.
- **Lembrete 3 dias**: cron diário 12:00 America/Sao_Paulo em `.emergent/crons.yml` → `POST /api/cron/checkin-reminder` (auth Bearer `WEBHOOK_CRON_SECRET`) → envia mensagem com PIX + link Stripe para reservas confirmadas/pendentes. Endpoint admin `/api/admin/cron/checkin-reminder/run` para trigger manual.
- **Visibilidade admin**: nova coluna "Reservado em" + "Origem" (Direto/Site/OTA) na lista; tooltip e popup do Calendário mostram guest + origem + data de criação + status.
- Testes: 11/11 backend + frontend ok (iteration_8.json). Tax mode selecionado: **DIY** (Stripe processa pagamento, sem auxílio fiscal; apropriado para hospedagem no Brasil onde o valor já inclui impostos).

### 2026-10-20 — Módulo RH & Escalas (/rh e /colaborador)
- Pedido do usuário: "módulo completo de RH e Escalas: escala 5x2, ponto eletrônico, férias, folha e dashboard do gestor", dentro do site atual em `/rh` e `/colaborador`, seguindo a CLT. Escolhas: ponto por botão no portal com data/hora/IP; INSS/IRRF como estimativa "prévia" pelas tabelas oficiais atuais.
- Corrigido o backend quebrado (`cal` não definido → `import calendar as cal`).
- `backend/hr_rules.py`: regras CLT puras (rodízio de domingos, feriados como folga, validação de interjornada de 11h, 7 dias seguidos, domingos seguidos, mais de 10h/dia, jornada semanal; cálculo do ponto com tolerância de 10 min, HE 50/100%, adicional noturno com hora reduzida, faltas + DSR; férias aquisitivo/concessivo, vencendo/vencida, frações e regras do art. 134; INSS 2026 + IRRF 2026 com redutor da Lei 15.270).
- Ponto: `POST /api/employee/punch` (sequência de 4 marcações, NSR sequencial, hash encadeado, IP), comprovante, espelho (RH e colaborador), ajustes e desconsideração com justificativa (o registro original nunca é apagado), PDF do espelho.
- Férias: o colaborador pede ou cancela, o RH aprova, recusa ou lança direto; quando aprovadas, viram "Férias" na escala.
- Folha (PRÉVIA): tabela por competência + holerite em PDF. Salário proporcional no mês da admissão.
- Dashboard RH: quem está trabalhando, em intervalo, atrasado ou de folga, com base no ponto; alertas de escala, férias e atrasos.
- Ao excluir um colaborador, ele passa a inativo (os registros de ponto ficam guardados, como exige a Portaria 671).
- Testes: iteration_9 (backend 30/30; frontend com correções aplicadas: erros 422 normalizados nos clientes axios e header da escala no mobile).

## Backlog / P1
- Widget de reserva na Home com seletor de datas + hóspedes.
- Auto-fill de endereço por CEP no FNRH.
- Manter override manual de porte de pet ao editar raça.
- Acessibilidade: `DialogDescription` em modais do admin.

## Backlog / P2
- Pacotes/upsells pagos.
- Link de auto-cancelamento por e-mail.
- Refatorar `server.py` (>2000 linhas) em routers.

## Backlog / P3
- Multi-idioma (EN/ES).
- Área do hóspede logado com histórico.

## Stripe — modo de impostos
- **Atual: DIY** — Stripe só processa o pagamento.
- Pode trocar quando quiser via chat (opções restantes: "Stripe calcula o imposto" +0,5% por transação).
- Chaves ativas são da sandbox claimable; para ir ao vivo, abrir **Manage → Payments** e completar o KYC (as chaves live substituem automaticamente no deploy).

## Credenciais de Teste
Ver `/app/memory/test_credentials.md`.
