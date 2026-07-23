document.addEventListener("DOMContentLoaded", () => {
const form = document.getElementById("churn-form");
const startAnalysisBtn = document.getElementById("start-analysis-btn");
const refreshMetricsBtn = document.getElementById("refresh-metrics-btn");
const conversationEl = document.getElementById("conversation");
const loading = document.getElementById("loading");
const formMessage = document.getElementById("form-message");
const metricsMessageEl = document.getElementById("metrics-message");
const metricsPredictionsEl = document.getElementById("metrics-predictions");
const metricsLatencyEl = document.getElementById("metrics-latency");
const metricsFallbacksEl = document.getElementById("metrics-fallbacks");
const metricsFallbackRateEl = document.getElementById("metrics-fallback-rate");
const metricsLowEl = document.getElementById("metrics-low");
const metricsMediumEl = document.getElementById("metrics-medium");
const metricsHighEl = document.getElementById("metrics-high");
const stepSections = Array.from(document.querySelectorAll(".step-card"));
const stepDots = Array.from(document.querySelectorAll(".step-dot"));
const step1Btn = document.getElementById("step-1-btn");
const step2Btn = document.getElementById("step-2-btn");
const submitBtn = document.getElementById("submit-btn");
const backToStep1Btn = document.getElementById("back-to-step-1-btn");
const backToStep2Btn = document.getElementById("back-to-step-2-btn");

const step1Fields = ["gender", "SeniorCitizen", "Partner", "Dependents"];
const step2Fields = [
  "tenure",
  "PhoneService",
  "MultipleLines",
  "InternetService",
  "OnlineSecurity",
  "OnlineBackup",
  "DeviceProtection",
  "TechSupport",
  "StreamingTV",
  "StreamingMovies",
  "Contract",
  "PaperlessBilling",
  "PaymentMethod",
];
const step3Fields = ["MonthlyCharges", "TotalCharges"];
const allFields = [...step1Fields, ...step2Fields, ...step3Fields];
let analysisFinished = false;
const fieldLabels = {
  gender: "Gênero",
  SeniorCitizen: "Pessoa idosa",
  Partner: "Possui parceiro",
  Dependents: "Possui dependentes",
  tenure: "Tempo de contrato (meses)",
  PhoneService: "Serviço de telefone",
  MultipleLines: "Várias linhas",
  InternetService: "Tipo de internet",
  OnlineSecurity: "Segurança online",
  OnlineBackup: "Backup online",
  DeviceProtection: "Proteção do dispositivo",
  TechSupport: "Suporte técnico",
  StreamingTV: "TV por streaming",
  StreamingMovies: "Filmes por streaming",
  Contract: "Plano",
  PaperlessBilling: "Cobrança digital",
  PaymentMethod: "Forma de pagamento",
  MonthlyCharges: "Valor mensal",
  TotalCharges: "Valor total acumulado",
};

function setLoading(isLoading) {
  loading.classList.toggle("hidden", !isLoading);
  form.classList.toggle("is-loading", isLoading);
  form.querySelectorAll("button").forEach((button) => {
    button.disabled = isLoading;
  });
}

function appendBubble(role, message) {
  const bubble = document.createElement("div");
  bubble.className = `bubble ${role}`;
  bubble.textContent = message;
  conversationEl.appendChild(bubble);
  conversationEl.scrollTop = conversationEl.scrollHeight;
}

function appendHtmlBubble(role, html) {
  const bubble = document.createElement("div");
  bubble.className = `bubble ${role} rich-bubble`;
  bubble.innerHTML = html;
  conversationEl.appendChild(bubble);
  conversationEl.scrollTop = conversationEl.scrollHeight;
}

function clearResults() {
  formMessage.textContent = "";
  analysisFinished = false;
  submitBtn.textContent = "Analisar cliente";
  submitBtn.type = "submit";
}

function setMetricsMessage(message, isError = false) {
  metricsMessageEl.textContent = message;
  metricsMessageEl.classList.toggle("error", isError);
}

function clearMetrics() {
  metricsPredictionsEl.textContent = "--";
  metricsLatencyEl.textContent = "--";
  metricsFallbacksEl.textContent = "--";
  metricsFallbackRateEl.textContent = "--";
  metricsLowEl.textContent = "0";
  metricsMediumEl.textContent = "0";
  metricsHighEl.textContent = "0";
  setMetricsMessage("");
}

function translateRisk(value) {
  const labels = {
    LOW: "Baixo",
    MEDIUM: "Médio",
    HIGH: "Alto",
  };
  return labels[value] || value;
}

function translateRead(value) {
  const labels = {
    LOW: "Cliente com baixa chance de sair",
    MEDIUM: "Cliente que merece atenção",
    HIGH: "Cliente com risco alto",
  };
  return labels[value] || value;
}

function formatLatency(value) {
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue)) {
    return "--";
  }
  return `${numericValue.toFixed(1)} ms`;
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text || "";
  return div.innerHTML;
}

function renderMarkdown(text) {
  const escaped = escapeHtml(text)
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/\n\s*\n/g, "</p><p>")
    .replace(/\n/g, "<br>");
  return `<p>${escaped}</p>`;
}

function renderRecommendationsHtml(items) {
  if (!items || items.length === 0) {
    return "";
  }
  const list = items.map((item) => `<li>${escapeHtml(item)}</li>`).join("");
  return `<h4>Recomendações</h4><ul>${list}</ul>`;
}

function renderResultBubble(data) {
  const probability = `${(data.probability * 100).toFixed(1)}%`;
  const risk = translateRisk(data.risk_class);
  const riskRead = translateRead(data.risk_class);
  const explanationHtml = renderMarkdown(data.explanation);
  const recommendationsHtml = renderRecommendationsHtml(data.recommendations);
  const fillClass = data.risk_class.toLowerCase();
  const fillWidth = Math.max(4, Math.round(data.probability * 100));

  return `
    <h4>Resultado da análise</h4>
    <div class="chat-kpis">
      <div class="chat-kpi probability-kpi">
        <span>Probabilidade de churn</span>
        <strong>${probability}</strong>
        <div class="probability-bar">
          <div class="probability-fill ${fillClass}" style="width: ${fillWidth}%"></div>
        </div>
      </div>
      <div class="chat-kpi">
        <span>Risco</span>
        <strong class="${fillClass}">${risk}</strong>
      </div>
      <div class="chat-kpi">
        <span>Leitura</span>
        <strong>${riskRead}</strong>
      </div>
    </div>
    ${explanationHtml}
    ${recommendationsHtml}
  `;
}

function setStep(stepNumber) {
  stepSections.forEach((section) => {
    const active = Number(section.dataset.step) === stepNumber;
    section.hidden = !active;
  });

  stepDots.forEach((dot, index) => {
    dot.classList.toggle("active", index < stepNumber);
  });

  formMessage.textContent = "";
}

function getFieldLabel(field) {
  if (field.tagName === "SELECT") {
    return field.selectedOptions[0]?.textContent.trim() || field.value;
  }
  return field.value;
}

function stepSummary(fields) {
  const items = fields
    .map((name) => {
      const field = form.elements.namedItem(name);
      if (!field || !("value" in field)) {
        return "";
      }
      return `<li><strong>${escapeHtml(fieldLabels[name] || name)}:</strong> ${escapeHtml(getFieldLabel(field))}</li>`;
    })
    .filter(Boolean)
    .join("");
  return `<ul class="summary-list">${items}</ul>`;
}

function validateFields(fieldNames) {
  for (const name of fieldNames) {
    const field = form.elements.namedItem(name);
    if (!(field instanceof HTMLInputElement || field instanceof HTMLSelectElement)) {
      continue;
    }
    if (!field.checkValidity()) {
      formMessage.textContent = "Preencha os campos obrigatórios antes de continuar.";
      field.reportValidity();
      return false;
    }
  }
  formMessage.textContent = "";
  return true;
}

function buildPayload() {
  const payload = {};

  allFields.forEach((fieldName) => {
    const field = form.elements.namedItem(fieldName);
    if (field && "value" in field) {
      payload[fieldName] = field.value;
    }
  });

  ["SeniorCitizen", "tenure", "MonthlyCharges", "TotalCharges"].forEach((field) => {
    if (payload[field] !== undefined) {
      payload[field] = Number(payload[field]);
    }
  });

  return payload;
}

async function loadMetrics() {
  try {
    const response = await fetch("/metrics");
    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || "Não foi possível carregar as métricas.");
    }

    metricsPredictionsEl.textContent = String(data.predictions ?? 0);
    metricsLatencyEl.textContent = formatLatency(data.average_latency_ms);
    metricsFallbacksEl.textContent = String(data.fallbacks ?? 0);
    metricsFallbackRateEl.textContent = `${((data.fallback_rate ?? 0) * 100).toFixed(1)}%`;
    metricsLowEl.textContent = String(data.risk_counts?.LOW ?? 0);
    metricsMediumEl.textContent = String(data.risk_counts?.MEDIUM ?? 0);
    metricsHighEl.textContent = String(data.risk_counts?.HIGH ?? 0);
    setMetricsMessage("Métricas atualizadas.");
  } catch (error) {
    setMetricsMessage(error.message || "Falha ao carregar as métricas.", true);
  }
}

async function analyzeClient(event) {
  event.preventDefault();
  if (analysisFinished) {
    resetAnalysis();
    return;
  }
  if (!validateFields(step3Fields)) {
    return;
  }

  clearResults();
  setLoading(true);

  const payload = buildPayload();

  try {
    const response = await fetch("/predict", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "Não foi possível analisar o cliente.");
    }

    loadMetrics();
    appendHtmlBubble("bot", renderResultBubble(data));
    analysisFinished = true;
    submitBtn.textContent = "Nova análise";
    submitBtn.type = "button";
  } catch (error) {
    formMessage.textContent = error.message || "Ocorreu um erro inesperado.";
  } finally {
    setLoading(false);
  }
}

step1Btn.addEventListener("click", () => {
  if (!validateFields(step1Fields)) {
    return;
  }

  appendHtmlBubble("user", `<h4>Perfil recebido</h4>${stepSummary(step1Fields)}`);
  appendBubble("bot", "Agora vamos aos serviços contratados.");
  setStep(2);
});

step2Btn.addEventListener("click", () => {
  if (!validateFields(step2Fields)) {
    return;
  }

  appendHtmlBubble("user", `<h4>Serviços recebidos</h4>${stepSummary(step2Fields)}`);
  appendBubble("bot", "Fechamos a última etapa com os valores da conta.");
  setStep(3);
});

backToStep1Btn.addEventListener("click", () => {
  setStep(1);
});

backToStep2Btn.addEventListener("click", () => {
  setStep(2);
});

form.addEventListener("submit", analyzeClient);
startAnalysisBtn.addEventListener("click", () => {
  stepSections[0].scrollIntoView({ behavior: "smooth", block: "start" });
  if (form.elements.gender) {
    form.elements.gender.focus();
  }
});
refreshMetricsBtn.addEventListener("click", loadMetrics);

function resetAnalysis() {
  form.reset();
  conversationEl.innerHTML = "";
  appendBubble("bot", "Primeiro preencha o perfil do cliente. Depois seguimos para serviços, valores e análise.");
  clearResults();
  setStep(1);
  stepSections[0].scrollIntoView({ behavior: "smooth", block: "start" });
}

submitBtn.addEventListener("click", (event) => {
  if (!analysisFinished) {
    return;
  }
  event.preventDefault();
  resetAnalysis();
});

clearResults();
clearMetrics();
setStep(1);
loadMetrics();
});
