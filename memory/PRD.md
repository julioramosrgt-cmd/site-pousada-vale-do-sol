# PRD - Sistema de Gestão de Pousada

## Problema
Proprietário de pousada precisa de site público + sistema completo de gestão: quartos, calendário unificado, formulário público FNRH, sincronização iCal com Airbnb/Booking/TripLar, templates WhatsApp com PIX, módulo financeiro (receitas/despesas) e gestão de galeria/configurações.

## User Personas
- Anfitrião/Recepção (admin): gerencia tudo pelo painel.
- Hóspede (público): navega pelo site e envia pré-reserva via formulário FNRH (write-only).

## Arquitetura
- Backend FastAPI + MongoDB, JWT auth, RBAC (admin vs público write-only), object storage (Emergent), icalendar parser/generator.
- Frontend React + Tailwind + shadcn/ui, react-router.
- Design: paleta terracotta + palm green + areia (evita gradientes roxo/azul genéricos).

## Implementado (2026-02-28)
- Auth JWT (`/api/auth/login`, `/me`, `/change-password`) com seed admin `admin@pousada.com / pousada2024`.
- Site público `/`: hero, sobre, acomodações, galeria com lightbox, contato, PIX copiar, floating WhatsApp.
- Formulário público FNRH `/reservar` (write-only, aceite obrigatório).
- Painel admin `/admin` com sidebar: Dashboard, Calendário (mês/semana), Reservas (CRUD + status + WhatsApp PIX 1-clique), Quartos (CRUD com comodidades/diária/status), Site & Galeria (URL + upload de arquivos), iCal (export por quarto + import de OTAs + sync manual), WhatsApp Templates (variáveis dinâmicas + preview + envio), Financeiro (receitas/despesas + resumo + ocupação), Conta (troca de senha).
- Object storage integrado para upload de fotos.
- iCal export/import bi-direcional pronto (sync manual - cron 15min pode ser adicionado depois).

## Backlog / P1
- Auto-sync iCal a cada 15 min (cron worker).
- Envio automático de e-mail via Resend após pré-reserva.
- Gráfico mensal financeiro (recharts) + exportação CSV.
- OpenGraph meta tags dinâmicas para /reservar.
- Roles multi-usuário (recepção vs admin) - hoje é admin único.
