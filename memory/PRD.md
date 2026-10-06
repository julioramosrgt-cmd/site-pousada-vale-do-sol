# PRD - Sistema de Gestão de Pousada Vale do Sol

## Problema
Proprietário de pousada precisa de site público + sistema completo de gestão: quartos, calendário unificado, formulário público FNRH, sincronização iCal com Airbnb/Booking/TripLar, templates WhatsApp com PIX, módulo financeiro (receitas/despesas) e gestão de galeria/configurações.

## User Personas
- Anfitrião/Recepção (admin): gerencia tudo pelo painel.
- Hóspede (público): navega pelo site e envia pré-reserva via formulário FNRH (write-only).

## Arquitetura
- Backend FastAPI + MongoDB, JWT auth, RBAC (admin vs público write-only), object storage (Emergent), icalendar parser/generator.
- Frontend React + Tailwind + shadcn/ui, react-router.
- Design: paleta terracotta + palm green + areia.

## Implementado
### 2026-02-28
- Auth JWT com seed admin, site público, formulário FNRH `/reservar`, painel admin completo, object storage, iCal export/import + auto-sync.

### Feb/2026 - Motor de Precificação + Pets
- `compute_pricing` custom: 10% sex/sáb, 2º adulto -10%, criança 0-3 1ª grátis / demais 65%, pets 20.7/27.6/34.5%.
- Classificação automática de 156 raças + fallback manual com aviso.
- Voucher PDF, QR code, WhatsApp webhook. Financeiro CSV/PDF.

### Feb/2026 - Autocomplete + Feriados Nacionais
- Autocomplete de raças (156) com navegação por teclado.
- Feriados nacionais BR (fixos + móveis via Páscoa Gregoriana) aplicam sobretaxa de 10%. Endpoint `GET /api/public/holidays`. Estimativa mostra "🎉 Nome do feriado".

### Feb/2026 - Formas de Pagamento (esta sessão)
- Nova seção "Formas de Pagamento" na home (`PublicSite.js`, âncora `#pagamento`) com ícone, texto sobre cartão de débito/crédito e CTA verde WhatsApp "Solicitar Link de Pagamento via WhatsApp" que abre `wa.me/{whatsapp}` com mensagem pré-preenchida.
- `data-testid="payment-methods-section"` e `data-testid="btn-request-payment-link"`.

## Backlog / P1
- Widget de reserva na Home com seletor de datas + hóspedes.
- Auto-fill de endereço por CEP no FNRH.
- Manter override manual de porte de pet ao editar raça.
- Acessibilidade: `DialogDescription` em modais do admin.

## Backlog / P2
- Pacotes/upsells (café premium, passeio) como add-ons pagos.
- Link de auto-cancelamento por e-mail dentro do prazo.
- Refatorar `server.py` em serviços (pricing/pdf/ical).

## Backlog / P3
- Multi-idioma (EN/ES).
- Área do hóspede logado com histórico.

## Credenciais de Teste
Ver `/app/memory/test_credentials.md`.
