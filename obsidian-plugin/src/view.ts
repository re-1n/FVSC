import { App, ItemView, Notice, WorkspaceLeaf } from "obsidian";
import type FvscPlugin from "./main";
import type { BackendController } from "./backend";
import { BootstrapModal } from "./bootstrap";

export const ANTOURAGE_VIEW_TYPE = "fvsc-antourage-view";

interface RuntimeStatus {
  loaded: boolean;
  source_count: number;
  ledger_events: number;
  active_events: number;
  exact_judgments: number;
  owner_feedback_events: number;
  snapshot_id: string | null;
}

interface BackendStatus {
  configured: boolean;
  backend_id: string | null;
  model: string | null;
  reachable: boolean | null;
  local_models: string[];
}

interface SearchHit {
  source_id: string;
  source_revision: string;
  source_kind: string;
  observed_at: number;
  score: number;
  preview: string;
  context_source_ids: string[];
  evidence_event_ids: string[];
}

interface SearchResponse {
  ranking: "lexical-char-ngram-v1";
  semantic_reranking: false;
  hits: SearchHit[];
}

interface ProposalCitation {
  citation_id: string;
  source_id: string;
  source_revision: string;
  start: number;
  end: number;
  text_sha256: string;
  evidence_event_ids: string[];
}

interface ProposalClaim {
  claim_id: string;
  text: string;
  citation_ids: string[];
  support_level: "evidence_bound" | "partially_supported" | "free_generation";
}

interface InterpretationProposal {
  proposal_id: string;
  answer: string;
  claims: ProposalClaim[];
  citations: ProposalCitation[];
  support_level: string;
  interpretation_layer: number;
  model: string | null;
  retrieval_method: string;
  defeasible: boolean;
}

interface ProposalAssessment {
  assessment_id: string;
  proposal_id: string;
  verdict: "accepted" | "partially_accepted" | "rejected" | "needs_revision";
  accepted_claim_ids: string[];
  rejected_claim_ids: string[];
}

const STATUS_POLL_MS = 5_000;

export class AntourageView extends ItemView {
  private queryInput: HTMLTextAreaElement | null = null;
  private resultEl: HTMLElement | null = null;
  private statusEl: HTMLElement | null = null;
  private backendEl: HTMLElement | null = null;
  private pollTimer: number | null = null;
  private requestAbort: AbortController | null = null;

  constructor(
    leaf: WorkspaceLeaf,
    private getBaseUrl: () => string,
    private getPlugin: () => FvscPlugin,
    private getBackend: () => BackendController,
  ) {
    super(leaf);
  }

  getViewType(): string {
    return ANTOURAGE_VIEW_TYPE;
  }

  getDisplayText(): string {
    return "FVSC Antourage";
  }

  getIcon(): string {
    return "git-fork";
  }

  async onOpen(): Promise<void> {
    for (const peer of this.app.workspace.getLeavesOfType(ANTOURAGE_VIEW_TYPE)) {
      if (peer.view !== this) peer.detach();
    }
    this.stopPolling();
    this.requestAbort?.abort();
    this.contentEl.empty();
    this.contentEl.addClass("fvsc-antourage-view");

    const toolbar = this.contentEl.createDiv({ cls: "fvsc-toolbar" });
    const syncButton = toolbar.createEl("button", {
      cls: "fvsc-toolbar-btn",
      text: "Синхронизировать",
    });
    syncButton.onclick = () => void this.synchronize(syncButton);
    const graphButton = toolbar.createEl("button", {
      cls: "fvsc-toolbar-btn",
      text: "Obsidian-граф",
    });
    graphButton.onclick = () => void this.openObsidianGraphSplit();
    const reloadButton = toolbar.createEl("button", {
      cls: "fvsc-toolbar-btn",
      text: "Обновить",
    });
    reloadButton.onclick = () => this.reload();

    const statusRow = this.contentEl.createDiv({ cls: "fvsc-runtime-status" });
    this.statusEl = statusRow.createDiv();
    this.backendEl = statusRow.createDiv();

    const composer = this.contentEl.createDiv({ cls: "fvsc-composer" });
    this.queryInput = composer.createEl("textarea", {
      cls: "fvsc-query",
      attr: {
        placeholder:
          "Вопрос к дневнику — например: какую роль играют паразиты в моих метафорах?",
        rows: "3",
      },
    });
    this.queryInput.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
        event.preventDefault();
        void this.interpret();
      }
    });
    const actions = composer.createDiv({ cls: "fvsc-composer-actions" });
    const searchButton = actions.createEl("button", { text: "Найти источники" });
    searchButton.onclick = () => void this.search(searchButton);
    const interpretButton = actions.createEl("button", {
      text: "Интерпретировать",
      cls: "mod-cta",
    });
    interpretButton.onclick = () => void this.interpret(interpretButton);
    actions.createSpan({
      cls: "fvsc-composer-hint",
      text: "Ctrl/⌘ + Enter — интерпретировать",
    });

    this.resultEl = this.contentEl.createDiv({ cls: "fvsc-results" });
    await this.refreshStatus();
    this.startPolling();
  }

  private async fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(`${this.getBaseUrl()}${path}`, init);
    if (!response.ok) {
      let detail = `HTTP ${response.status}`;
      try {
        const body = await response.json() as { detail?: string };
        if (body.detail) detail = body.detail;
      } catch { /* keep generic detail */ }
      throw new Error(detail);
    }
    return await response.json() as T;
  }

  private async refreshStatus(): Promise<void> {
    try {
      const [runtime, backend] = await Promise.all([
        this.fetchJson<RuntimeStatus>("/v1/status"),
        this.fetchJson<BackendStatus>("/v1/interpretation/status"),
      ]);
      if (this.statusEl) {
        this.statusEl.empty();
        this.statusEl.createSpan({
          text: runtime.loaded
            ? `${runtime.source_count} источников · ${runtime.exact_judgments} relations`
            : "Vault ещё не синхронизирован",
        });
        if (!runtime.loaded) {
          const button = this.statusEl.createEl("button", { text: "Начать" });
          button.onclick = () => void BootstrapModal.maybeShow(
            this.getPlugin(),
            this.getBackend(),
            () => this.reload(),
          );
        }
      }
      this.renderBackendStatus(backend);
    } catch {
      if (this.statusEl) this.statusEl.setText("Локальный FVSC-сервис недоступен");
    }
  }

  private renderBackendStatus(status: BackendStatus): void {
    if (!this.backendEl) return;
    this.backendEl.empty();
    if (!status.configured) {
      this.backendEl.setText("Интерпретатор выключен");
      return;
    }
    if (status.reachable === false) {
      this.backendEl.createSpan({ text: "Ollama недоступна · " });
      const link = this.backendEl.createEl("a", {
        text: "установить / запустить",
        href: "https://ollama.com/download",
      });
      link.setAttr("target", "_blank");
      link.setAttr("rel", "noopener");
      return;
    }
    const configured = status.model || "модель не выбрана";
    if (status.local_models.length === 0) {
      this.backendEl.setText(`Ollama · ${configured}`);
      return;
    }
    const select = this.backendEl.createEl("select", { cls: "fvsc-model-select" });
    for (const model of status.local_models) {
      const option = select.createEl("option", { text: model, value: model });
      option.selected = model === configured;
    }
    if (!status.local_models.includes(configured)) {
      const option = select.createEl("option", { text: `${configured} (не найдена)`, value: configured });
      option.selected = true;
    }
    select.onchange = () => void this.selectModel(select.value);
  }

  private async selectModel(model: string): Promise<void> {
    const plugin = this.getPlugin();
    plugin.settings.modelName = model;
    await plugin.saveSettings();
    new Notice(`FVSC: выбрана ${model}; перезапускаю сервис.`);
    await this.getBackend().restart();
    await this.refreshStatus();
  }

  private query(): string {
    return this.queryInput?.value.trim() || "";
  }

  private async synchronize(button?: HTMLButtonElement): Promise<void> {
    if (button) button.disabled = true;
    this.setBusy("Синхронизирую vault…");
    try {
      const status = await this.fetchJson<RuntimeStatus>("/v1/vault/sync", {
        method: "POST",
      });
      new Notice(`FVSC: ${status.source_count} источников синхронизировано`);
      await this.refreshStatus();
      this.renderEmpty("Синхронизация завершена. Теперь можно искать и интерпретировать.");
    } catch (error) {
      this.renderError(error);
    } finally {
      if (button) button.disabled = false;
    }
  }

  private async search(button?: HTMLButtonElement): Promise<void> {
    const query = this.query();
    if (!query) {
      new Notice("FVSC: введи вопрос или фразу для поиска.");
      return;
    }
    if (button) button.disabled = true;
    this.requestAbort?.abort();
    this.requestAbort = new AbortController();
    this.setBusy("Ищу исходные сообщения…");
    try {
      const result = await this.fetchJson<SearchResponse>("/v1/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, top_k: 10, context_depth: 1 }),
        signal: this.requestAbort.signal,
      });
      this.renderSearch(result);
    } catch (error) {
      if ((error as { name?: string }).name !== "AbortError") this.renderError(error);
    } finally {
      if (button) button.disabled = false;
    }
  }

  private async interpret(button?: HTMLButtonElement): Promise<void> {
    const question = this.query();
    if (!question) {
      new Notice("FVSC: введи вопрос к дневнику.");
      return;
    }
    if (button) button.disabled = true;
    this.requestAbort?.abort();
    this.requestAbort = new AbortController();
    this.setBusy("Нахожу источники и строю проверяемую интерпретацию…");
    try {
      const proposal = await this.fetchJson<InterpretationProposal>("/v1/interpret", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, top_k: 5, context_depth: 1 }),
        signal: this.requestAbort.signal,
      });
      this.renderProposal(proposal);
    } catch (error) {
      if ((error as { name?: string }).name !== "AbortError") this.renderError(error);
    } finally {
      if (button) button.disabled = false;
    }
  }

  private setBusy(message: string): void {
    if (!this.resultEl) return;
    this.resultEl.empty();
    this.resultEl.createDiv({ cls: "fvsc-busy", text: message });
  }

  private renderEmpty(message: string): void {
    if (!this.resultEl) return;
    this.resultEl.empty();
    this.resultEl.createDiv({ cls: "fvsc-empty-result", text: message });
  }

  private renderError(error: unknown): void {
    if (!this.resultEl) return;
    this.resultEl.empty();
    this.resultEl.createDiv({ cls: "fvsc-error", text: `Ошибка: ${String(error)}` });
  }

  private renderSearch(result: SearchResponse): void {
    if (!this.resultEl) return;
    this.resultEl.empty();
    const heading = this.resultEl.createDiv({ cls: "fvsc-result-heading" });
    heading.createEl("h3", { text: "Исходные фрагменты" });
    heading.createSpan({
      text: "lexical baseline · без semantic reranking",
      cls: "fvsc-method",
    });
    if (result.hits.length === 0) {
      this.renderEmpty("Совпадений нет — FVSC воздержался.");
      return;
    }
    for (const hit of result.hits) this.renderSourceHit(hit);
  }

  private renderSourceHit(hit: SearchHit): void {
    if (!this.resultEl) return;
    const card = this.resultEl.createDiv({ cls: "fvsc-source-card" });
    const head = card.createDiv({ cls: "fvsc-source-head" });
    const source = head.createEl("button", { cls: "fvsc-source-link", text: hit.source_id });
    source.onclick = () => void this.openSource(hit.source_id);
    head.createSpan({ text: `${(hit.score * 100).toFixed(1)}%`, cls: "fvsc-score" });
    card.createEl("p", { text: hit.preview });
    if (hit.context_source_ids.length > 0) {
      const context = card.createDiv({ cls: "fvsc-context" });
      context.createSpan({ text: "Контекст: " });
      for (const sourceId of hit.context_source_ids) {
        const button = context.createEl("button", { text: sourceId });
        button.onclick = () => void this.openSource(sourceId);
      }
    }
  }

  private renderProposal(proposal: InterpretationProposal): void {
    if (!this.resultEl) return;
    this.resultEl.empty();
    const heading = this.resultEl.createDiv({ cls: "fvsc-result-heading" });
    heading.createEl("h3", { text: "Предложенная интерпретация" });
    heading.createSpan({
      text: `L${proposal.interpretation_layer} · ${proposal.model || "backend"} · отменяема`,
      cls: "fvsc-method",
    });
    this.resultEl.createEl("p", { text: proposal.answer, cls: "fvsc-answer" });

    const citations = new Map(proposal.citations.map((citation) => [citation.citation_id, citation]));
    const list = this.resultEl.createDiv({ cls: "fvsc-claims" });
    const accepted = new Set<string>();
    const rejected = new Set<string>();
    const claimCards = new Map<string, HTMLElement>();
    for (const claim of proposal.claims) {
      const card = list.createDiv({ cls: "fvsc-claim-card" });
      claimCards.set(claim.claim_id, card);
      const support = card.createSpan({
        text: this.supportLabel(claim.support_level),
        cls: `fvsc-support fvsc-support-${claim.support_level}`,
      });
      support.setAttr("title", claim.support_level);
      card.createEl("p", { text: claim.text });
      const links = card.createDiv({ cls: "fvsc-citations" });
      for (const citationId of claim.citation_ids) {
        const citation = citations.get(citationId);
        if (!citation) continue;
        const button = links.createEl("button", { text: citation.source_id });
        button.setAttr("title", `символы ${citation.start}–${citation.end}`);
        button.onclick = () => void this.openSource(citation.source_id);
      }
      if (claim.citation_ids.length === 0) {
        links.createSpan({ text: "без источника" });
      }
      const actions = card.createDiv({ cls: "fvsc-claim-actions" });
      const accept = actions.createEl("button", { text: "Принять" });
      const reject = actions.createEl("button", { text: "Отклонить" });
      accept.onclick = () => {
        accepted.add(claim.claim_id);
        rejected.delete(claim.claim_id);
        this.markClaimDecision(card, "accepted");
      };
      reject.onclick = () => {
        rejected.add(claim.claim_id);
        accepted.delete(claim.claim_id);
        this.markClaimDecision(card, "rejected");
      };
    }
    const review = this.resultEl.createDiv({ cls: "fvsc-review" });
    const save = review.createEl("button", { text: "Сохранить мою оценку", cls: "mod-cta" });
    const reviewStatus = review.createSpan({ cls: "fvsc-review-status" });
    save.onclick = async () => {
      save.disabled = true;
      try {
        const all = proposal.claims.length;
        const verdict =
          accepted.size === all ? "accepted"
          : rejected.size === all ? "rejected"
          : accepted.size > 0 ? "partially_accepted"
          : "needs_revision";
        const assessment = await this.fetchJson<ProposalAssessment>("/v1/interpret/assess", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            proposal_id: proposal.proposal_id,
            case_id: `interactive:${proposal.proposal_id.slice(0, 16)}`,
            verdict,
            accepted_claim_ids: Array.from(accepted),
            rejected_claim_ids: Array.from(rejected),
            reason_tags: ["owner-reviewed"],
          }),
        });
        reviewStatus.setText(`Сохранено: ${this.verdictLabel(assessment.verdict)}`);
        for (const claimId of assessment.accepted_claim_ids) {
          const card = claimCards.get(claimId);
          if (card) this.markClaimDecision(card, "accepted");
        }
        for (const claimId of assessment.rejected_claim_ids) {
          const card = claimCards.get(claimId);
          if (card) this.markClaimDecision(card, "rejected");
        }
      } catch (error) {
        reviewStatus.setText(`Не сохранено: ${String(error)}`);
      } finally {
        save.disabled = false;
      }
    };
    const foot = this.resultEl.createDiv({ cls: "fvsc-proposal-foot" });
    foot.setText(
      "Это предложение Антуража, не запись в вашей канонической памяти. " +
      "Оценка claims хранится отдельно и не переписывает исходники.",
    );
  }

  private markClaimDecision(
    card: HTMLElement,
    decision: "accepted" | "rejected",
  ): void {
    card.removeClass("fvsc-claim-accepted", "fvsc-claim-rejected");
    card.addClass(`fvsc-claim-${decision}`);
  }

  private verdictLabel(verdict: ProposalAssessment["verdict"]): string {
    if (verdict === "accepted") return "всё принято";
    if (verdict === "partially_accepted") return "принято частично";
    if (verdict === "rejected") return "всё отклонено";
    return "нужна пересборка";
  }

  private supportLabel(level: ProposalClaim["support_level"]): string {
    if (level === "evidence_bound") return "опирается на текст";
    if (level === "partially_supported") return "частично гипотеза";
    return "свободная гипотеза";
  }

  private async openSource(sourceId: string): Promise<void> {
    await this.app.workspace.openLinkText(sourceId, "", true);
  }

  private startPolling(): void {
    if (this.pollTimer !== null) return;
    this.pollTimer = window.setInterval(() => void this.refreshStatus(), STATUS_POLL_MS);
  }

  private stopPolling(): void {
    if (this.pollTimer !== null) window.clearInterval(this.pollTimer);
    this.pollTimer = null;
  }

  reload(): void {
    void this.onOpen();
  }

  private async openObsidianGraphSplit(): Promise<void> {
    const app = this.app as App;
    const existing = app.workspace.getLeavesOfType("graph");
    if (existing.length > 0) {
      app.workspace.revealLeaf(existing[0]);
      return;
    }
    const leaf = app.workspace.getLeaf("split", "vertical");
    await leaf.setViewState({ type: "graph", active: true });
    app.workspace.revealLeaf(leaf);
  }

  async onClose(): Promise<void> {
    this.stopPolling();
    this.requestAbort?.abort();
    this.contentEl.empty();
    this.queryInput = null;
    this.resultEl = null;
    this.statusEl = null;
    this.backendEl = null;
  }
}
