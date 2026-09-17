/**
 * Lógica Completa da Aplicação Web Oficial - Prêmio "Padrão do Ano" (COMARA)
 * Implementação integral das 5 fases eleitorais, fila DPTI e autenticação LDAP.
 */

const appState = {
  usuarioAtual: null,
  faseAtual: "FASE_1_SECAO",
  faseInfo: null,
  eleitorFase4: null,
  votosFase4: {
    Graduados: null,
    Pracas: null,
    Civil: null
  },
  cedulaCandidatos: {
    Graduados: [],
    Pracas: [],
    Civil: []
  },
  efetivoGeral: []
};

// ==========================================
// SISTEMA DE NOTIFICAÇÕES VISUAIS (TOASTS)
// ==========================================
function showToast(title, message, type = "info", duration = 4500) {
  const container = document.getElementById("toast-container");
  if (!container) return;

  const icons = {
    success: "✅",
    warning: "⚠️",
    error: "❌",
    info: "ℹ️"
  };
  const icon = icons[type] || "ℹ️";

  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `
    <div class="toast-icon">${icon}</div>
    <div class="toast-content">
      <div class="toast-title">${escapeHtml(title)}</div>
      <div class="toast-message">${escapeHtml(message)}</div>
    </div>
    <button type="button" class="toast-close" aria-label="Fechar">&times;</button>
  `;

  const btnClose = toast.querySelector(".toast-close");
  const removeToast = () => {
    toast.classList.add("toast-hide");
    setTimeout(() => {
      if (toast.parentNode) toast.parentNode.removeChild(toast);
    }, 280);
  };

  btnClose.addEventListener("click", removeToast);
  container.appendChild(toast);

  if (duration > 0) {
    setTimeout(removeToast, duration);
  }
}

// ==========================================
// INICIALIZAÇÃO
// ==========================================
document.addEventListener("DOMContentLoaded", () => {
  initNavegacaoAbas();
  initModalAuthTabs();
  initEventosAuth();
  initEventosDPTI();
  initEventosFasesControle();
  initEventosFase4();
  initEventosAuditoria();

  // Tenta login automático padrão como Administrador
  loginAutomaticoPadrao();
});

// ==========================================
// MODAL DE AUTENTICAÇÃO (LOGIN LDAP & AUTO-CADASTRO)
// ==========================================
function initModalAuthTabs() {
  const btnTabLogin = document.getElementById("tab-btn-modal-login");
  const btnTabCad = document.getElementById("tab-btn-modal-cadastro");
  const paneLogin = document.getElementById("modal-pane-login");
  const paneCad = document.getElementById("modal-pane-cadastro");

  if (!btnTabLogin || !btnTabCad) return;

  btnTabLogin.addEventListener("click", () => {
    btnTabLogin.style.borderBottom = "3px solid var(--primary-blue)";
    btnTabLogin.style.color = "var(--primary-blue)";
    btnTabCad.style.borderBottom = "3px solid transparent";
    btnTabCad.style.color = "var(--text-secondary)";
    paneLogin.style.display = "block";
    paneCad.style.display = "none";
  });

  btnTabCad.addEventListener("click", () => {
    btnTabCad.style.borderBottom = "3px solid var(--primary-blue)";
    btnTabCad.style.color = "var(--primary-blue)";
    btnTabLogin.style.borderBottom = "3px solid transparent";
    btnTabLogin.style.color = "var(--text-secondary)";
    paneLogin.style.display = "none";
    paneCad.style.display = "block";
  });
}

function abrirModalLogin() {
  const modal = document.getElementById("modal-auth");
  if (modal) {
    modal.style.display = "flex";
    document.getElementById("login-ldap-feedback").innerHTML = "";
    document.getElementById("login-ldap-user").focus();
  }
}

function fecharModalLogin() {
  const modal = document.getElementById("modal-auth");
  if (modal) modal.style.display = "none";
}

window.preencherLoginDemo = function(user, pass) {
  document.getElementById("login-ldap-user").value = user;
  document.getElementById("login-ldap-pass").value = pass;
  document.getElementById("btn-submit-ldap").click();
};

function initEventosAuth() {
  // Login LDAP
  const formLogin = document.getElementById("form-login-ldap");
  if (formLogin) {
    formLogin.addEventListener("submit", handleLoginLdap);
  }

  // Auto-Cadastro
  const formCad = document.getElementById("form-auto-cadastro");
  if (formCad) {
    formCad.addEventListener("submit", handleAutoCadastro);
  }

  // Trocar usuário
  const btnTrocar = document.getElementById("btn-trocar-usuario");
  if (btnTrocar) {
    btnTrocar.addEventListener("click", abrirModalLogin);
  }
}

async function loginAutomaticoPadrao() {
  try {
    const res = await fetch("/api/auth/login-ldap", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ldap_username: "admin.dpti", password: "comara" })
    });
    if (res.ok) {
      const data = await res.json();
      aplicarUsuarioLogado(data);
    } else {
      abrirModalLogin();
    }
  } catch (err) {
    abrirModalLogin();
  }
}

async function handleLoginLdap(e) {
  e.preventDefault();
  const username = document.getElementById("login-ldap-user").value.trim();
  const password = document.getElementById("login-ldap-pass").value;
  const feedback = document.getElementById("login-ldap-feedback");
  feedback.innerHTML = "";

  const btn = document.getElementById("btn-submit-ldap");
  btn.disabled = true;
  btn.innerHTML = "<span>⏳</span> Autenticando...";

  try {
    const res = await fetch("/api/auth/login-ldap", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ldap_username: username, password: password })
    });
    const data = await res.json();

    if (!res.ok) {
      if (res.status === 403 && data.detail && data.detail.includes("NÃO FOI LIBERADO")) {
        feedback.innerHTML = `
          <div class="alert alert-danger" style="margin-top:0.75rem; text-align: left;">
            <span style="font-size: 1.5rem;">🛑</span>
            <div>
              <strong>ACESSO BLOQUEADO - PENDÊNCIA NA DPTI:</strong><br>
              ${data.detail}
            </div>
          </div>
        `;
        return;
      }
      throw new Error(data.detail || "Usuário ou senha incorretos.");
    }

    aplicarUsuarioLogado(data);
    fecharModalLogin();
  } catch (err) {
    feedback.innerHTML = `<div class="alert alert-danger" style="margin-top:0.75rem;"><span>⚠️</span> <div>${err.message}</div></div>`;
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<span>🔑</span> Entrar no Sistema`;
  }
}

async function handleAutoCadastro(e) {
  e.preventDefault();
  const feedback = document.getElementById("auto-cadastro-feedback");
  feedback.innerHTML = "";

  const payload = {
    nome_completo: document.getElementById("cad-nome-completo").value.trim(),
    nome_guerra: document.getElementById("cad-nome-guerra").value.trim(),
    identificador: document.getElementById("cad-identificador").value.trim(),
    tipo: document.getElementById("cad-tipo").value,
    posto_grad_cargo: document.getElementById("cad-posto").value.trim(),
    categoria: document.getElementById("cad-categoria").value,
    divisao: document.getElementById("cad-divisao").value,
    secao: document.getElementById("cad-secao").value.trim().toUpperCase(),
    tempo_comara_meses: 12,
    ldap_username: document.getElementById("cad-ldap-username").value.trim(),
    senha: document.getElementById("cad-senha").value
  };

  try {
    const res = await fetch("/api/auth/auto-cadastro", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();

    if (!res.ok) {
      throw new Error(data.detail || "Falha ao registrar auto-cadastro.");
    }

    feedback.innerHTML = `
      <div class="alert alert-warning" style="margin-top:0.75rem; text-align: left;">
        <span style="font-size: 1.5rem;">📝</span>
        <div>
          <strong>CADASTRO REGISTRADO COM SUCESSO!</strong><br>
          ${data.mensagem}<br><br>
          <em>Status: <strong>PENDENTE_DPTI</strong>. O login permanecerá bloqueado até que o Administrador da DPTI confirme a ativação.</em>
        </div>
      </div>
    `;

    showToast("Cadastro Efetuado!", "Seu cadastro foi enviado à DPTI para liberação presencial.", "info", 5000);
    document.getElementById("form-auto-cadastro").reset();
  } catch (err) {
    feedback.innerHTML = `<div class="alert alert-danger" style="margin-top:0.75rem;"><span>⚠️</span> <div>${err.message}</div></div>`;
    showToast("Erro no Cadastro", err.message, "error", 5000);
  }
}

function aplicarUsuarioLogado(user) {
  appState.usuarioAtual = user;

  // Atualizar cabeçalho
  const badgeRole = document.getElementById("user-role-badge");
  badgeRole.textContent = user.papel;
  badgeRole.className = "user-badge-role";

  if (user.papel === "ADMINISTRADOR") badgeRole.classList.add("role-admin");
  else if (user.papel === "CMDT_OM") badgeRole.classList.add("role-cmdt");
  else if (user.papel === "CHEFE_DIVISAO") badgeRole.classList.add("role-chefe-div");
  else if (user.papel === "CHEFE_SECAO") badgeRole.classList.add("role-chefe-sec");
  else badgeRole.classList.add("role-usuario");

  document.getElementById("user-name-display").textContent = `${user.posto_grad_cargo || ''} ${user.nome_guerra || user.nome_completo}`;
  document.getElementById("user-unit-display").textContent = `(${user.divisao || 'COMARA'}${user.secao ? ' / ' + user.secao : ''})`;

  // Visibilidade de controle de fases (Apenas Administrador e Comandante da OM)
  const ctrlBox = document.getElementById("controle-fase-admin-box");
  if (ctrlBox) {
    ctrlBox.style.display = (user.papel === "ADMINISTRADOR" || user.papel === "CMDT_OM") ? "flex" : "none";
  }

  // Preencher identificador na cabine de votação
  const inputSaramF4 = document.getElementById("fase4-input-saram");
  if (inputSaramF4 && user.identificador) {
    inputSaramF4.value = user.identificador;
  }

  // Configurar abas e redirecionar conforme modificador de acesso
  configurarPermissoesAbas(user.papel);
  carregarStatusFases();
}

function configurarPermissoesAbas(papel) {
  const btnDpti = document.getElementById("nav-btn-dpti");
  const btnFase1 = document.getElementById("nav-btn-fase1");
  const btnFase2 = document.getElementById("nav-btn-fase2");
  const btnFase3 = document.getElementById("nav-btn-fase3");
  const btnFase4 = document.getElementById("nav-btn-fase4");
  const btnFase5 = document.getElementById("nav-btn-fase5");
  const btnAuditoria = document.getElementById("nav-btn-auditoria");

  // Restaura visibilidade inicial
  [btnDpti, btnFase1, btnFase2, btnFase3, btnFase4, btnFase5, btnAuditoria].forEach(b => {
    if (b) b.style.display = "inline-flex";
  });

  const cardFilaDpti = document.getElementById("card-fila-dpti");

  if (papel === "ADMINISTRADOR") {
    if (cardFilaDpti) cardFilaDpti.style.display = "block";
    btnDpti.click();
  } else if (papel === "CMDT_OM") {
    if (cardFilaDpti) cardFilaDpti.style.display = "none";
    btnDpti.style.display = "none";
    btnFase1.style.display = "none";
    btnFase2.style.display = "none";
    btnFase3.style.display = "none";
    btnFase5.click();
  } else if (papel === "CHEFE_DIVISAO") {
    if (cardFilaDpti) cardFilaDpti.style.display = "none";
    btnDpti.style.display = "none";
    btnFase1.style.display = "none";
    btnFase5.style.display = "none";
    btnAuditoria.style.display = "none";
    btnFase2.click();
  } else if (papel === "CHEFE_SECAO") {
    if (cardFilaDpti) cardFilaDpti.style.display = "none";
    btnDpti.style.display = "none";
    btnFase2.style.display = "none";
    btnFase3.style.display = "none";
    btnFase5.style.display = "none";
    btnAuditoria.style.display = "none";
    btnFase1.click();
  } else {
    // USUARIO_COMUM
    if (cardFilaDpti) cardFilaDpti.style.display = "none";
    btnDpti.style.display = "none";
    btnFase1.style.display = "none";
    btnFase2.style.display = "none";
    btnFase3.style.display = "none";
    btnFase5.style.display = "none";
    btnAuditoria.style.display = "none";
    btnFase4.click();
  }
}

// ==========================================
// CONTROLE DE NAVEGAÇÃO DE ABAS
// ==========================================
function initNavegacaoAbas() {
  const tabs = document.querySelectorAll(".nav-tab-btn");
  tabs.forEach(tab => {
    tab.addEventListener("click", () => {
      tabs.forEach(t => t.classList.remove("active"));
      document.querySelectorAll(".tab-pane").forEach(p => p.classList.remove("active"));

      tab.classList.add("active");
      const targetId = tab.getAttribute("data-tab");
      const pane = document.getElementById(targetId);
      if (pane) pane.classList.add("active");

      // Carga de dados sob demanda conforme a aba selecionada
      if (targetId === "tab-dpti") {
        carregarFilaDpti();
        carregarTabelaEfetivo();
      } else if (targetId === "tab-fase1") {
        carregarFase1();
      } else if (targetId === "tab-fase2") {
        carregarFase2();
      } else if (targetId === "tab-fase3") {
        carregarFase3();
      } else if (targetId === "tab-fase4") {
        carregarCabineFase4();
      } else if (targetId === "tab-fase5") {
        carregarFase5();
      } else if (targetId === "tab-auditoria") {
        carregarLogsAuditoria();
      }
    });
  });
}

// ==========================================
// CONTROLE DAS 5 FASES ELEITORAIS
// ==========================================
function initEventosFasesControle() {
  const btnAvancar = document.getElementById("btn-avancar-fase");
  if (btnAvancar) {
    btnAvancar.addEventListener("click", handleAvancarFase);
  }
}

async function carregarStatusFases() {
  try {
    const res = await fetch("/api/fases/status");
    if (!res.ok) return;
    const data = await res.json();
    appState.faseAtual = data.fase_atual;
    appState.faseInfo = data;

    // Atualizar seletor administrativo
    const select = document.getElementById("select-avancar-fase");
    if (select) select.value = data.fase_atual;

    // Atualizar stepper de fases no topo
    const mapping = {
      "FASE_1_SECAO": "badge-fase-1",
      "FASE_2_DIVISAO": "badge-fase-2",
      "FASE_3_VETO": "badge-fase-3",
      "FASE_4_VOTACAO_GERAL": "badge-fase-4",
      "FASE_5_COMANDANTE": "badge-fase-5",
      "FINALIZADO": "badge-fase-5"
    };

    [1, 2, 3, 4, 5].forEach(num => {
      const el = document.getElementById(`badge-fase-${num}`);
      if (el) el.classList.remove("active");
    });

    const activeId = mapping[data.fase_atual];
    if (activeId) {
      const el = document.getElementById(activeId);
      if (el) el.classList.add("active");
    }
  } catch (err) {
    console.error("Erro ao carregar status das fases:", err);
  }
}

async function handleAvancarFase() {
  const novaFase = document.getElementById("select-avancar-fase").value;
  if (!confirm(`Deseja alterar a fase oficial do processo eleitoral para:\n"${novaFase}"?`)) {
    return;
  }

  try {
    const res = await fetch("/api/fases/avancar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        nova_fase: novaFase,
        usuario_admin: appState.usuarioAtual ? appState.usuarioAtual.ldap_username : "admin.dpti"
      })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Erro ao avançar fase.");

    showToast("Fase Alterada com Sucesso!", `O processo eleitoral avançou para: ${data.nome}`, "success");
    await carregarStatusFases();

    // Recarrega a aba atual
    const activeTab = document.querySelector(".nav-tab-btn.active");
    if (activeTab) activeTab.click();
  } catch (err) {
    showToast("Falha ao Alterar Fase", err.message, "error", 6000);
  }
}

// ==========================================
// ABA 1: FILA DPTI & VÍNCULO LDAP + EFETIVO
// ==========================================
function initEventosDPTI() {
  const btnAtualizarFila = document.getElementById("btn-atualizar-fila-dpti");
  if (btnAtualizarFila) {
    btnAtualizarFila.addEventListener("click", carregarFilaDpti);
  }

  const btnAtualizarEfetivo = document.getElementById("btn-atualizar-efetivo");
  if (btnAtualizarEfetivo) {
    btnAtualizarEfetivo.addEventListener("click", carregarTabelaEfetivo);
  }

  const filtroDiv = document.getElementById("filtro-tabela-divisao");
  const filtroCat = document.getElementById("filtro-tabela-categoria");
  if (filtroDiv) filtroDiv.addEventListener("change", carregarTabelaEfetivo);
  if (filtroCat) filtroCat.addEventListener("change", carregarTabelaEfetivo);

  // Modal DPTI liberar
  const formModalLiberar = document.getElementById("form-dpti-liberar-modal");
  if (formModalLiberar) {
    formModalLiberar.addEventListener("submit", handleConfirmarLiberacaoDpti);
  }
}

async function carregarFilaDpti() {
  const corpo = document.getElementById("tabela-fila-dpti-corpo");
  if (!corpo) return;
  corpo.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-muted);">Consultando cadastros na DPTI...</td></tr>`;

  try {
    const res = await fetch("/api/admin/dpti-fila");
    if (!res.ok) throw new Error("Erro ao obter fila da DPTI.");
    const usuarios = await res.json();

    if (usuarios.length === 0) {
      corpo.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-muted);">Nenhum usuário cadastrado na fila da DPTI.</td></tr>`;
      return;
    }

    corpo.innerHTML = usuarios.map(u => {
      const isPendente = u.status === "PENDENTE_DPTI";
      const badgeStatus = isPendente 
        ? `<span class="badge badge-warning" style="background:#fef3c7; color:#b45309;">⚠️ PENDENTE DPTI</span>`
        : `<span class="badge badge-homologado" style="background:#dcfce7; color:#15803d;">✅ ATIVO</span>`;

      return `
        <tr style="${isPendente ? 'background: #fffbeb;' : ''}">
          <td>
            <strong>${escapeHtml(u.nome_completo)}</strong>
            ${isPendente ? '<br><small style="color:#b45309; font-weight:600;">Aguardando validação presencial</small>' : ''}
          </td>
          <td><code>${escapeHtml(u.identificador)}</code></td>
          <td><strong>${escapeHtml(u.ldap_username)}</strong></td>
          <td>${escapeHtml(u.divisao || '-')}${u.secao ? ' / ' + escapeHtml(u.secao) : ''}</td>
          <td>${badgeStatus}</td>
          <td style="text-align: center;">
            <button class="btn ${isPendente ? 'btn-gold' : 'btn-secondary'} btn-sm" onclick="abrirModalDptiLiberar(${u.id}, '${escapeHtml(u.nome_completo)}', '${escapeHtml(u.identificador)}', '${escapeHtml(u.ldap_username)}', '${escapeHtml(u.papel)}', '${escapeHtml(u.divisao || 'DE')}', '${escapeHtml(u.secao || '')}', '${u.status}')">
              <span>${isPendente ? '🔓' : '⚙️'}</span> ${isPendente ? 'Liberar Acesso' : 'Editar Papel'}
            </button>
          </td>
        </tr>
      `;
    }).join("");
  } catch (err) {
    corpo.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--danger);">Falha: ${err.message}</td></tr>`;
  }
}

window.abrirModalDptiLiberar = function(id, nome, identificador, ldap, papel, divisao, secao, status) {
  document.getElementById("dpti-modal-usuario-id").value = id;
  document.getElementById("dpti-modal-nome").textContent = nome;
  document.getElementById("dpti-modal-identificador").textContent = identificador;
  document.getElementById("dpti-modal-ldap").value = ldap;
  document.getElementById("dpti-modal-papel").value = papel || "USUARIO_COMUM";
  document.getElementById("dpti-modal-divisao").value = divisao || "DE";
  document.getElementById("dpti-modal-secao").value = secao || "";
  document.getElementById("dpti-modal-feedback").innerHTML = "";

  const statusBadge = document.getElementById("dpti-modal-status-badge");
  statusBadge.textContent = status;
  statusBadge.className = status === "PENDENTE_DPTI" ? "badge badge-warning" : "badge badge-homologado";

  document.getElementById("modal-dpti-liberar").style.display = "flex";
};

window.fecharModalDptiLiberar = function() {
  document.getElementById("modal-dpti-liberar").style.display = "none";
};

async function handleConfirmarLiberacaoDpti(e) {
  e.preventDefault();
  const feedback = document.getElementById("dpti-modal-feedback");
  feedback.innerHTML = "";

  const payload = {
    usuario_id: parseInt(document.getElementById("dpti-modal-usuario-id").value, 10),
    ldap_username: document.getElementById("dpti-modal-ldap").value.trim().toLowerCase(),
    papel: document.getElementById("dpti-modal-papel").value,
    divisao: document.getElementById("dpti-modal-divisao").value,
    secao: document.getElementById("dpti-modal-secao").value.trim().toUpperCase(),
    admin_username: appState.usuarioAtual ? appState.usuarioAtual.ldap_username : "admin.dpti"
  };

  try {
    const res = await fetch("/api/admin/dpti-liberar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Erro ao liberar usuário.");

    showToast("Credenciamento Concluído!", data.mensagem, "success");
    fecharModalDptiLiberar();
    carregarFilaDpti();
    carregarTabelaEfetivo();
  } catch (err) {
    feedback.innerHTML = `<div class="alert alert-danger" style="margin-top:0.75rem;"><span>⚠️</span> <div>${err.message}</div></div>`;
    showToast("Erro no Credenciamento", err.message, "error");
  }
}

async function carregarTabelaEfetivo() {
  const div = document.getElementById("filtro-tabela-divisao").value;
  const cat = document.getElementById("filtro-tabela-categoria").value;
  const corpo = document.getElementById("tabela-efetivo-corpo");
  if (!corpo) return;

  corpo.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-muted);">Consultando registros do efetivo...</td></tr>`;

  try {
    let url = "/api/efetivo?";
    if (div) url += `divisao=${encodeURIComponent(div)}&`;
    if (cat) url += `categoria=${encodeURIComponent(cat)}&`;

    const res = await fetch(url);
    if (!res.ok) throw new Error("Erro ao consultar efetivo.");
    const dados = await res.json();
    appState.efetivoGeral = dados;

    if (dados.length === 0) {
      corpo.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-muted);">Nenhum militar ou civil encontrado com estes filtros.</td></tr>`;
      return;
    }

    corpo.innerHTML = dados.map(m => {
      let badgeCat = "badge-graduados";
      if (m.categoria === "Pracas") badgeCat = "badge-pracas";
      if (m.categoria === "Civil") badgeCat = "badge-civil";

      return `
        <tr>
          <td><strong>${escapeHtml(m.posto_grad_cargo)}</strong></td>
          <td>${escapeHtml(m.nome_guerra)}</td>
          <td><code>${escapeHtml(m.identificador)}</code></td>
          <td><span class="badge ${badgeCat}">${escapeHtml(m.categoria)}</span></td>
          <td><strong>${escapeHtml(m.divisao)}</strong></td>
          <td>${escapeHtml(m.secao)}</td>
          <td>${m.tempo_comara_meses} meses</td>
        </tr>
      `;
    }).join("");
  } catch (err) {
    corpo.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--danger);">Falha: ${err.message}</td></tr>`;
  }
}

// ==========================================
// ABA 2: FASE 1 - INDICAÇÃO POR SEÇÃO (1 POR CLASSE)
// ==========================================
async function carregarFase1() {
  const container = document.getElementById("container-fase1-classes");
  const badgeSecao = document.getElementById("fase1-secao-badge");
  if (!container) return;

  const secaoAlvo = (appState.usuarioAtual && appState.usuarioAtual.secao) ? appState.usuarioAtual.secao : "DEPL";
  if (badgeSecao) badgeSecao.textContent = `Seção: ${secaoAlvo}`;

  container.innerHTML = `<div style="text-align:center; padding: 2rem; color: var(--text-muted);">Consultando subordinados da Seção ${secaoAlvo}...</div>`;

  try {
    const res = await fetch(`/api/fase1/meus-subordinados?secao=${encodeURIComponent(secaoAlvo)}`);
    if (!res.ok) throw new Error("Erro ao buscar subordinados da seção.");
    const data = await res.json();

    const categoriasConfig = [
      { id: "Graduados", nome: "Graduado Padrão (SO / SGT)", badge: "badge-graduados" },
      { id: "Pracas", nome: "Praça Padrão (SD / CB)", badge: "badge-pracas" },
      { id: "Civil", nome: "Civil Padrão (SPPF / SPTF)", badge: "badge-civil" }
    ];

    let html = "";
    categoriasConfig.forEach(cat => {
      const membros = data.membros_por_categoria[cat.id] || [];
      const indicadoId = data.indicacoes_feitas[cat.id];

      html += `
        <div class="card" style="margin-bottom: 1.5rem; border-left: 4px solid var(--primary-blue);">
          <div class="card-header">
            <div>
              <h3 class="card-title" style="font-size: 1.05rem;">${cat.nome}</h3>
              <p class="card-subtitle">Subordinados diretos da Seção <strong>${escapeHtml(secaoAlvo)}</strong></p>
            </div>
            <span class="badge ${cat.badge}">${membros.length} subordinado(s)</span>
          </div>
      `;

      if (membros.length === 0) {
        html += `<p style="color: var(--text-muted); font-size: 0.85rem;">Nenhum integrante desta classe lotado na Seção ${escapeHtml(secaoAlvo)}.</p>`;
      } else {
        if (membros.length === 1) {
          html += `
            <div class="alert alert-warning" style="font-size: 0.82rem; margin-bottom: 0.75rem;">
              <span>ℹ️</span>
              <div><strong>Único Integrante:</strong> Por ser o único membro da seção nesta classe, sua qualificação para a próxima etapa é prioritária.</div>
            </div>
          `;
        }

        html += `<div class="grid-3">`;
        membros.forEach(m => {
          const isIndicado = (indicadoId === m.id);
          html += `
            <div class="candidate-card ${isIndicado ? 'selected-candidate-card' : ''}" style="display:flex; flex-direction:column; justify-content:space-between;">
              <div>
                <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.5rem;">
                  <span class="badge ${cat.badge}">${escapeHtml(m.posto_grad_cargo)}</span>
                  ${isIndicado ? '<span class="badge badge-homologado">⭐ INDICADO</span>' : ''}
                </div>
                <div style="font-weight: 700; font-size: 1rem; color: var(--primary-navy);">${escapeHtml(m.nome_guerra)}</div>
                <div style="font-size: 0.8rem; color: var(--text-secondary); margin-bottom: 0.4rem;">${escapeHtml(m.nome)}</div>
                <div style="font-size: 0.78rem; color: var(--text-muted);">
                  Identificador: <code>${escapeHtml(m.identificador)}</code><br>
                  Tempo COMARA: ${m.tempo_comara_meses} meses
                </div>
              </div>
              <div style="margin-top: 1rem;">
                <button class="btn ${isIndicado ? 'btn-secondary' : 'btn-primary'} btn-sm" style="width: 100%;" 
                  onclick="handleIndicarFase1('${escapeHtml(secaoAlvo)}', '${cat.id}', ${m.id}, '${escapeHtml(m.posto_grad_cargo)} ${escapeHtml(m.nome_guerra)}')">
                  <span>${isIndicado ? '✓' : '👉'}</span> ${isIndicado ? 'Manter Indicação' : 'Indicar Subordinado'}
                </button>
              </div>
            </div>
          `;
        });
        html += `</div>`;
      }

      html += `</div>`;
    });

    container.innerHTML = html;
  } catch (err) {
    container.innerHTML = `<div class="alert alert-danger"><span>⚠️</span> <div>Falha ao carregar subordinados: ${err.message}</div></div>`;
  }
}

window.handleIndicarFase1 = async function(secao, categoria, candidatoId, nomeCandidato) {
  if (!appState.usuarioAtual || (appState.usuarioAtual.papel !== "CHEFE_SECAO" && appState.usuarioAtual.papel !== "ADMINISTRADOR")) {
    showToast("Acesso Restrito", "Apenas Chefes de Seção ou Administradores podem indicar subordinados na Fase 1.", "warning", 5000);
    return;
  }

  if (!confirm(`Confirmar a indicação de ${nomeCandidato} como o representante oficial da Seção ${secao} na classe ${categoria}?`)) {
    return;
  }

  try {
    const res = await fetch("/api/fase1/indicar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        secao: secao,
        categoria: categoria,
        candidato_id: candidatoId,
        ldap_username: appState.usuarioAtual ? appState.usuarioAtual.ldap_username : "secao.depl"
      })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Erro ao salvar indicação.");

    showToast("Indicação Registrada!", data.mensagem, "success");
    carregarFase1();
  } catch (err) {
    showToast("Falha na Indicação", err.message, "error", 6000);
  }
};

// ==========================================
// ABA 3: FASE 2 - SELEÇÃO POR CHEFE DE DIVISÃO (ATÉ 2 POR CLASSE)
// ==========================================
async function carregarFase2() {
  const container = document.getElementById("container-fase2-classes");
  const badgeDiv = document.getElementById("fase2-divisao-badge");
  if (!container) return;

  const divisaoAlvo = (appState.usuarioAtual && appState.usuarioAtual.divisao) ? appState.usuarioAtual.divisao : "DE";
  if (badgeDiv) badgeDiv.textContent = `Divisão: ${divisaoAlvo}`;

  container.innerHTML = `<div style="text-align:center; padding: 2rem; color: var(--text-muted);">Carregando indicados pelas seções subordinadas à Divisão ${divisaoAlvo}...</div>`;

  try {
    const res = await fetch(`/api/fase2/indicados-secoes?divisao=${encodeURIComponent(divisaoAlvo)}`);
    if (!res.ok) throw new Error("Erro ao carregar indicados das seções.");
    const data = await res.json();

    const categoriasConfig = [
      { id: "Graduados", nome: "Graduado Padrão (SO / SGT)", badge: "badge-graduados" },
      { id: "Pracas", nome: "Praça Padrão (SD / CB)", badge: "badge-pracas" },
      { id: "Civil", nome: "Civil Padrão (SPPF / SPTF)", badge: "badge-civil" }
    ];

    let html = "";
    categoriasConfig.forEach(cat => {
      const indicados = data.indicados_por_categoria[cat.id] || [];
      const selecionados = data.selecionados_fase2[cat.id] || [];

      html += `
        <div class="card" style="margin-bottom: 1.5rem; border-left: 4px solid var(--accent-gold);">
          <div class="card-header">
            <div>
              <h3 class="card-title" style="font-size: 1.05rem;">${cat.nome}</h3>
              <p class="card-subtitle">Indicados pelas seções da Divisão <strong>${escapeHtml(divisaoAlvo)}</strong> &bull; Escolha até <strong>2 representantes</strong></p>
            </div>
            <span class="badge ${cat.badge}">${indicados.length} indicado(s) pelas seções</span>
          </div>
      `;

      if (indicados.length === 0) {
        html += `<p style="color: var(--text-muted); font-size: 0.85rem;">Nenhuma seção da Divisão ${escapeHtml(divisaoAlvo)} indicou candidatos nesta classe ainda na Fase 1.</p>`;
      } else {
        html += `
          <form onsubmit="handleSalvarFase2(event, '${escapeHtml(divisaoAlvo)}', '${cat.id}')">
            <div class="grid-3" style="margin-bottom: 1rem;">
        `;

        indicados.forEach(cand => {
          const isChecked = selecionados.includes(cand.id);
          html += `
            <label class="candidate-card" style="cursor: pointer; display: flex; gap: 0.75rem; align-items: flex-start;">
              <input type="checkbox" name="fase2_check_${cat.id}" value="${cand.id}" ${isChecked ? 'checked' : ''} style="margin-top: 0.25rem; width: 1.2rem; height: 1.2rem;" onchange="limitarSelecaoFase2(this, '${cat.id}')">
              <div style="flex: 1;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.3rem;">
                  <span class="badge ${cat.badge}">${escapeHtml(cand.posto_grad_cargo)}</span>
                  <span class="badge badge-civil">Seção ${escapeHtml(cand.secao_origem)}</span>
                </div>
                <div style="font-weight: 700; font-size: 1rem; color: var(--primary-navy);">${escapeHtml(cand.nome_guerra)}</div>
                <div style="font-size: 0.8rem; color: var(--text-secondary);">${escapeHtml(cand.nome)}</div>
                <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 0.3rem;">
                  Tempo COMARA: ${cand.tempo_comara_meses} meses
                </div>
              </div>
            </label>
          `;
        });

        html += `
            </div>
            <button type="submit" class="btn btn-gold btn-sm">
              <span>💾</span> Salvar Representantes da Divisão (${cat.nome})
            </button>
          </form>
        `;
      }

      html += `</div>`;
    });

    container.innerHTML = html;
  } catch (err) {
    container.innerHTML = `<div class="alert alert-danger"><span>⚠️</span> <div>Falha: ${err.message}</div></div>`;
  }
}

window.limitarSelecaoFase2 = function(checkbox, catId) {
  const checks = document.querySelectorAll(`input[name="fase2_check_${catId}"]:checked`);
  if (checks.length > 2) {
    showToast(
      "Limite de Representantes Atingido!",
      "O regulamento da Fase 2 permite que o Chefe de Divisão selecione no MÁXIMO 2 representantes por classe.",
      "warning",
      5000
    );
    checkbox.checked = false;
  }
};

window.handleSalvarFase2 = async function(e, divisao, categoria) {
  e.preventDefault();
  if (!appState.usuarioAtual || (appState.usuarioAtual.papel !== "CHEFE_DIVISAO" && appState.usuarioAtual.papel !== "ADMINISTRADOR")) {
    showToast("Acesso Restrito", "Apenas Chefes de Divisão ou Administradores podem homologar representantes na Fase 2.", "warning", 5000);
    return;
  }

  const checkboxes = document.querySelectorAll(`input[name="fase2_check_${categoria}"]:checked`);
  const ids = Array.from(checkboxes).map(cb => parseInt(cb.value, 10));

  if (ids.length === 0) {
    if (!confirm("Nenhum candidato selecionado. Deseja zerar as indicações da divisão para esta classe?")) {
      return;
    }
  }

  try {
    const res = await fetch("/api/fase2/selecionar-divisao", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        divisao: divisao,
        categoria: categoria,
        candidato_ids: ids,
        ldap_username: appState.usuarioAtual ? appState.usuarioAtual.ldap_username : "moreira.cde"
      })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Erro ao salvar representantes.");

    showToast("Representantes Registrados!", data.mensagem, "success");
    carregarFase2();
  } catch (err) {
    showToast("Falha ao Salvar", err.message, "error", 6000);
  }
};

// ==========================================
// ABA 4: FASE 3 - RODADA DE VETO DAS CHEFIAS DE DIVISÃO
// ==========================================
async function carregarFase3() {
  const container = document.getElementById("container-fase3-vetos");
  if (!container) return;

  const chefeLdap = appState.usuarioAtual ? appState.usuarioAtual.ldap_username : "";
  container.innerHTML = `<div style="text-align:center; padding: 2rem; color: var(--text-muted);">Carregando deliberações de veto das Chefias de Divisão...</div>`;

  try {
    const res = await fetch(`/api/fase3/candidatos-veto?chefe_ldap=${encodeURIComponent(chefeLdap)}`);
    if (!res.ok) throw new Error("Erro ao consultar dados de veto.");
    const data = await res.json();

    const categoriasConfig = [
      { id: "Graduados", nome: "Graduado Padrão (SO / SGT)", badge: "badge-graduados" },
      { id: "Pracas", nome: "Praça Padrão (SD / CB)", badge: "badge-pracas" },
      { id: "Civil", nome: "Civil Padrão (SPPF / SPTF)", badge: "badge-civil" }
    ];

    const podeVotarVeto = (appState.usuarioAtual && (appState.usuarioAtual.papel === "CHEFE_DIVISAO" || appState.usuarioAtual.papel === "ADMINISTRADOR"));

    let html = "";
    categoriasConfig.forEach(cat => {
      const candidatos = data.candidatos_por_categoria[cat.id] || [];

      html += `
        <div class="card" style="margin-bottom: 1.5rem; border-left: 4px solid #6366f1;">
          <div class="card-header">
            <div>
              <h3 class="card-title" style="font-size: 1.05rem;">${cat.nome}</h3>
              <p class="card-subtitle">Total de Chefes Votantes: ${data.total_chefes} Divisões</p>
            </div>
            <span class="badge ${cat.badge}">${candidatos.length} candidato(s)</span>
          </div>
      `;

      if (candidatos.length === 0) {
        html += `<p style="color: var(--text-muted); font-size: 0.85rem;">Nenhum candidato homologado pelas Divisões para a Fase 3 nesta classe.</p>`;
      } else {
        html += `<div class="grid-3">`;
        candidatos.forEach(cand => {
          const isVetoAprovado = cand.status_veto === "APROVADO_PARA_VOTACAO";
          const badgeStatus = isVetoAprovado
            ? `<span class="badge badge-homologado" style="background:#dcfce7; color:#15803d;">✅ Aprovado p/ Votação</span>`
            : `<span class="badge badge-danger" style="background:#fee2e2; color:#b91c1c;">⛔ VETADO</span>`;

          const meuVoto = cand.meu_voto; // 1 = Veto, 0 = Não veta, null = pendente

          html += `
            <div class="candidate-card" style="display:flex; flex-direction:column; justify-content:space-between; border-color: ${meuVoto === 1 ? '#fca5a5' : (meuVoto === 0 ? '#86efac' : 'var(--border-color)')};">
              <div>
                <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.4rem;">
                  <span class="badge ${cat.badge}">${escapeHtml(cand.posto_grad_cargo)}</span>
                  <span class="badge badge-civil">Divisão ${escapeHtml(cand.divisao)}</span>
                </div>
                <div style="font-weight: 700; font-size: 1rem; color: var(--primary-navy);">${escapeHtml(cand.nome_guerra)}</div>
                <div style="font-size: 0.8rem; color: var(--text-secondary); margin-bottom: 0.5rem;">${escapeHtml(cand.nome)}</div>
                
                <div style="background:#f8fafc; padding: 0.6rem; border-radius: var(--radius); border: 1px solid var(--border-color); font-size: 0.8rem; margin-bottom: 0.75rem;">
                  <div style="display: flex; justify-content: space-between; margin-bottom: 0.2rem;">
                    <span>Placar de Vetos:</span>
                    <strong>${cand.total_vetos} de ${cand.limite_veto_maioria * 2} chefes</strong>
                  </div>
                  <div style="display: flex; justify-content: space-between;">
                    <span>Status Atual:</span>
                    ${badgeStatus}
                  </div>
                </div>

                ${meuVoto !== null && meuVoto !== undefined ? `
                  <div style="font-size: 0.78rem; text-align: center; margin-bottom: 0.6rem; color: ${meuVoto === 1 ? 'var(--danger)' : 'var(--success)'}; font-weight: 700;">
                    Seu Voto Registrado: ${meuVoto === 1 ? '⛔ VOCÊ VETOU' : '✅ VOCÊ APROVOU (NÃO VETOU)'}
                  </div>
                ` : ''}
              </div>

              ${podeVotarVeto ? `
                <div style="display: flex; gap: 0.4rem; margin-top: 0.5rem;">
                  <button class="btn btn-sm ${meuVoto === 0 ? 'btn-primary' : 'btn-secondary'}" style="flex: 1;" onclick="handleVotarVeto(${cand.id}, 0)">
                    <span>✅</span> Não Vetar
                  </button>
                  <button class="btn btn-sm ${meuVoto === 1 ? 'btn-danger' : 'btn-secondary'}" style="flex: 1; border-color: #fca5a5; color: #dc2626;" onclick="handleVotarVeto(${cand.id}, 1)">
                    <span>⛔</span> Vetar
                  </button>
                </div>
              ` : `
                <div style="font-size: 0.75rem; color: var(--text-muted); text-align: center;">Apenas Chefes de Divisão deliberam o voto de veto.</div>
              `}
            </div>
          `;
        });
        html += `</div>`;
      }

      html += `</div>`;
    });

    container.innerHTML = html;
  } catch (err) {
    container.innerHTML = `<div class="alert alert-danger"><span>⚠️</span> <div>Falha: ${err.message}</div></div>`;
  }
}

window.handleVotarVeto = async function(candidatoId, votoVeto) {
  if (!appState.usuarioAtual || (appState.usuarioAtual.papel !== "CHEFE_DIVISAO" && appState.usuarioAtual.papel !== "ADMINISTRADOR")) {
    showToast("Acesso Restrito", "Apenas Chefes de Divisão ou Administradores têm prerrogativa de voto na Rodada de Veto.", "warning", 5000);
    return;
  }

  const acaoTexto = votoVeto === 1 ? "VETAR" : "NÃO VETAR (Aprovar)";
  if (!confirm(`Deseja registrar o voto de "${acaoTexto}" para este candidato?`)) {
    return;
  }

  try {
    const res = await fetch("/api/fase3/votar-veto", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        candidato_id: candidatoId,
        voto_veto: votoVeto,
        ldap_username: appState.usuarioAtual ? appState.usuarioAtual.ldap_username : "moreira.cde"
      })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Erro ao registrar voto de veto.");

    showToast("Deliberação Registrada!", `Seu voto (${acaoTexto}) foi computado no colegiado de Chefes de Divisão.`, "success");
    carregarFase3();
  } catch (err) {
    showToast("Falha na Votação de Veto", err.message, "error", 6000);
  }
};

// ==========================================
// ABA 5: FASE 4 - CABINE DE VOTAÇÃO GERAL POR CLIQUE (SEM NOTAS)
// ==========================================
function initEventosFase4() {
  const formAuthInline = document.getElementById("form-fase4-auth-inline");
  if (formAuthInline) {
    formAuthInline.addEventListener("submit", handleTrocarEleitorFase4Submit);
  }

  const formVotarF4 = document.getElementById("form-fase4-votar");
  if (formVotarF4) {
    formVotarF4.addEventListener("submit", handleSubmeterVotoFase4);
  }

  const btnProxEleitor = document.getElementById("btn-fase4-proximo-eleitor");
  if (btnProxEleitor) {
    btnProxEleitor.addEventListener("click", resetCabineVotacaoFase4);
  }
}

window.toggleTrocarEleitorFase4 = function(forcar = null) {
  const box = document.getElementById("fase4-box-trocar-eleitor");
  if (!box) return;
  if (forcar !== null) {
    box.style.display = forcar ? "block" : "none";
  } else {
    box.style.display = box.style.display === "none" ? "block" : "none";
  }
  if (box.style.display === "block") {
    const input = document.getElementById("fase4-input-saram");
    if (input) {
      input.focus();
      input.select();
    }
  }
};

async function handleTrocarEleitorFase4Submit(e) {
  e.preventDefault();
  const ident = document.getElementById("fase4-input-saram").value.trim();
  const feedback = document.getElementById("fase4-auth-feedback");
  if (feedback) feedback.innerHTML = "";

  if (!ident) {
    showToast("Identificador Obrigatório", "Por favor, digite o SARAM ou CPF do votante.", "warning");
    if (feedback) feedback.innerHTML = `<div class="alert alert-warning">Digite o SARAM do militar ou CPF do servidor civil.</div>`;
    return;
  }

  // Se efetivo geral ainda não estiver em memória, busca na API
  if (!appState.efetivoGeral || appState.efetivoGeral.length === 0) {
    try {
      const r = await fetch("/api/efetivo");
      appState.efetivoGeral = await r.json();
    } catch (err) {}
  }

  const identLimpo = ident.replace(/\./g, "").replace(/-/g, "").trim().toLowerCase();
  const eleitor = appState.efetivoGeral.find(m => {
    const saramLimpo = (m.identificador || "").replace(/\./g, "").replace(/-/g, "").trim().toLowerCase();
    const ldapLimpo = (m.ldap_username || "").trim().toLowerCase();
    return saramLimpo === identLimpo || ldapLimpo === identLimpo;
  });

  if (!eleitor) {
    showToast("Eleitor Não Localizado", `O SARAM/CPF "${ident}" não foi encontrado no efetivo cadastrado na DPTI.`, "error");
    if (feedback) {
      feedback.innerHTML = `
        <div class="alert alert-danger" style="margin-top: 0.5rem;">
          <span>⚠️</span>
          <div><strong>Identificador não cadastrado:</strong> Verifique se o número digitado está correto ou realize o credenciamento prévio na DPTI.</div>
        </div>
      `;
    }
    return;
  }

  appState.eleitorFase4 = eleitor;
  appState.votosFase4 = { Graduados: null, Pracas: null, Civil: null };

  atualizarCabecalhoEleitorFase4();
  renderizarCartoesCedulaClique("Graduados", "cedula-fase4-graduados", "badge-graduados");
  renderizarCartoesCedulaClique("Pracas", "cedula-fase4-pracas", "badge-pracas");
  renderizarCartoesCedulaClique("Civil", "cedula-fase4-civil", "badge-civil");
  atualizarPillsProgressoFase4();

  toggleTrocarEleitorFase4(false);
  showToast("Eleitor Habilitado na Cabine", `${eleitor.posto_grad_cargo} ${eleitor.nome_guerra} (${eleitor.divisao}) pronto para votar.`, "success");
}

function atualizarCabecalhoEleitorFase4() {
  const elNome = document.getElementById("fase4-eleitor-nome");
  const elDiv = document.getElementById("fase4-eleitor-divisao");
  const elIdent = document.getElementById("fase4-eleitor-identificador");
  const inputSaram = document.getElementById("fase4-input-saram");

  const eleitor = appState.eleitorFase4 || appState.usuarioAtual;
  if (eleitor) {
    if (elNome) elNome.textContent = `${eleitor.posto_grad_cargo || ''} ${eleitor.nome_guerra || eleitor.nome_completo || 'Eleitor Desconhecido'}`;
    if (elDiv) elDiv.textContent = `${eleitor.divisao || 'COMARA'}${eleitor.secao ? ' / ' + eleitor.secao : ''}`;
    if (elIdent) elIdent.textContent = eleitor.identificador || eleitor.ldap_username || '--';
    if (inputSaram && eleitor.identificador) inputSaram.value = eleitor.identificador;
  } else {
    if (elNome) elNome.textContent = "Nenhum eleitor identificado";
    if (elDiv) elDiv.textContent = "--";
    if (elIdent) elIdent.textContent = "--";
  }
}

function atualizarPillsProgressoFase4() {
  const configs = [
    { cat: "Graduados", pillId: "pill-status-graduados", badgeId: "badge-escolha-graduados", rotulo: "Graduados" },
    { cat: "Pracas", pillId: "pill-status-pracas", badgeId: "badge-escolha-pracas", rotulo: "Praças" },
    { cat: "Civil", pillId: "pill-status-civil", badgeId: "badge-escolha-civil", rotulo: "Civil" }
  ];

  configs.forEach(cfg => {
    const pill = document.getElementById(cfg.pillId);
    const badge = document.getElementById(cfg.badgeId);
    const candId = appState.votosFase4[cfg.cat];

    if (candId) {
      const cand = (appState.cedulaCandidatos[cfg.cat] || []).find(c => c.id === candId);
      const nomeGuerra = cand ? `${cand.posto_grad_cargo} ${cand.nome_guerra}` : "Candidato #" + candId;
      if (pill) {
        pill.className = "vote-tracker-pill ready";
        pill.innerHTML = `${cfg.rotulo}: 🟢 ${nomeGuerra}`;
      }
      if (badge) {
        badge.className = "badge badge-homologado";
        badge.style.background = "#dcfce7";
        badge.style.color = "#15803d";
        badge.innerHTML = `✅ Selecionado: ${nomeGuerra}`;
      }
    } else {
      if (pill) {
        pill.className = "vote-tracker-pill pending";
        pill.innerHTML = `${cfg.rotulo}: ⚪ Pendente`;
      }
      if (badge) {
        badge.className = "badge badge-warning";
        badge.style.background = "#fef3c7";
        badge.style.color = "#b45309";
        badge.innerHTML = `⚪ Pendente de Escolha`;
      }
    }
  });
}

async function carregarCabineFase4() {
  // 1. Vincula eleitor padrão a partir do usuário logado se ainda não definido
  if (!appState.eleitorFase4 && appState.usuarioAtual) {
    appState.eleitorFase4 = appState.usuarioAtual;
  }

  // 2. Atualiza dados do cabeçalho
  atualizarCabecalhoEleitorFase4();

  // 3. Alerta de fase inativa (caso não seja Fase 4)
  const alertaFase = document.getElementById("fase4-alerta-fase-inativa");
  const nomeFaseAtual = document.getElementById("fase4-nome-fase-atual");
  if (alertaFase) {
    if (appState.faseAtual !== "FASE_4_VOTACAO_GERAL") {
      alertaFase.style.display = "flex";
      if (nomeFaseAtual) {
        nomeFaseAtual.textContent = appState.faseInfo ? appState.faseInfo.nome_fase : appState.faseAtual;
      }
    } else {
      alertaFase.style.display = "none";
    }
  }

  // 4. Obtém os candidatos homologados da cédula se ainda não carregados
  await carregarCedulaFase4();

  // 5. Renderiza os cartões de cada uma das 3 classes imediatamente (sem tela intermediária!)
  renderizarCartoesCedulaClique("Graduados", "cedula-fase4-graduados", "badge-graduados");
  renderizarCartoesCedulaClique("Pracas", "cedula-fase4-pracas", "badge-pracas");
  renderizarCartoesCedulaClique("Civil", "cedula-fase4-civil", "badge-civil");

  // 6. Atualiza os pills de progresso
  atualizarPillsProgressoFase4();

  // 7. Garante visibilidade da cédula direta
  const boxCedula = document.getElementById("fase4-box-cedula");
  const boxComp = document.getElementById("fase4-box-comprovante");
  if (boxCedula) boxCedula.style.display = "block";
  if (boxComp) boxComp.style.display = "none";
}

async function carregarCedulaFase4() {
  try {
    const res = await fetch("/api/fase4/cedula-geral");
    if (!res.ok) throw new Error("Erro ao obter cédula eleitoral.");
    const data = await res.json();
    appState.cedulaCandidatos = data.candidatos_cedula;
  } catch (err) {
    console.error("Erro ao carregar candidatos da cédula:", err);
  }
}

function renderizarCartoesCedulaClique(catId, containerId, badgeClass) {
  const container = document.getElementById(containerId);
  if (!container) return;

  const candidatos = appState.cedulaCandidatos[catId] || [];

  if (candidatos.length === 0) {
    container.innerHTML = `
      <div style="grid-column: 1 / -1; padding: 1.5rem; background: #f8fafc; border: 1px dashed var(--border-color); border-radius: var(--radius); text-align: center; color: var(--text-muted);">
        <span>ℹ️</span> Nenhum candidato homologado pelas Chefias de Divisão na Fase 3 para esta classe até o momento.
      </div>
    `;
    return;
  }

  const votoAtual = appState.votosFase4[catId];

  container.innerHTML = candidatos.map(c => {
    const isSelecionado = (votoAtual === c.id);
    return `
      <div class="candidate-card ${isSelecionado ? 'selected-candidate-card' : ''}" id="card-cand-${catId}-${c.id}" 
           style="cursor: pointer; transition: all 0.2s ease; border: 2px solid ${isSelecionado ? 'var(--primary-blue)' : 'var(--border-color)'}; background: ${isSelecionado ? '#f0f7ff' : 'var(--bg-card)'};" 
           onclick="selecionarCandidatoClique('${catId}', ${c.id})">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
          <span class="badge ${badgeClass}">${escapeHtml(c.posto_grad_cargo)}</span>
          <span class="badge badge-civil">Divisão ${escapeHtml(c.divisao)}</span>
        </div>
        <div style="font-weight: 700; font-size: 1.05rem; color: var(--primary-navy); margin-bottom: 0.2rem;">${escapeHtml(c.nome_guerra)}</div>
        <div style="font-size: 0.82rem; color: var(--text-secondary); margin-bottom: 0.5rem;">${escapeHtml(c.nome)}</div>
        <div style="font-size: 0.75rem; color: var(--text-muted);">Tempo COMARA: ${c.tempo_comara_meses} meses</div>
        <div id="check-icon-${catId}-${c.id}" style="margin-top: 0.75rem; text-align: center; font-size: 0.85rem; font-weight: 700; color: ${isSelecionado ? 'var(--primary-blue)' : 'var(--text-muted)'};">
          ${isSelecionado ? '🔵 <strong>VOTO SELECIONADO</strong>' : '⚪ Clique para Escolher'}
        </div>
      </div>
    `;
  }).join("");
}

window.selecionarCandidatoClique = function(catId, candId) {
  appState.votosFase4[catId] = candId;

  // Atualiza cartões visualmente
  const candidatos = appState.cedulaCandidatos[catId] || [];
  let candidatoEscolhido = null;
  candidatos.forEach(c => {
    const card = document.getElementById(`card-cand-${catId}-${c.id}`);
    const check = document.getElementById(`check-icon-${catId}-${c.id}`);
    if (card && check) {
      if (c.id === candId) {
        candidatoEscolhido = c;
        card.classList.add("selected-candidate-card");
        card.style.borderColor = "var(--primary-blue)";
        card.style.background = "#f0f7ff";
        check.innerHTML = "🔵 <strong>VOTO SELECIONADO</strong>";
        check.style.color = "var(--primary-blue)";
      } else {
        card.classList.remove("selected-candidate-card");
        card.style.borderColor = "var(--border-color)";
        card.style.background = "var(--bg-card)";
        check.innerHTML = "⚪ Clique para Escolher";
        check.style.color = "var(--text-muted)";
      }
    }
  });

  // Remove animação de falta se estava ativa
  const boxCat = document.getElementById(`categoria-box-${catId}`);
  if (boxCat) {
    boxCat.classList.remove("missing-category-pulse");
  }

  // Limpa alerta de erro inline se houver
  const avisoFalha = document.getElementById("fase4-voto-aviso-falha");
  if (avisoFalha) avisoFalha.innerHTML = "";

  // Atualiza os pills no topo
  atualizarPillsProgressoFase4();

  // Feedback imediato ao usuário
  if (candidatoEscolhido) {
    showToast(
      "Voto Selecionado",
      `Classe ${catId}: ${candidatoEscolhido.posto_grad_cargo} ${candidatoEscolhido.nome_guerra} selecionado.`,
      "info",
      2200
    );
  }
};

async function handleSubmeterVotoFase4(e) {
  e.preventDefault();
  const avisoFalha = document.getElementById("fase4-voto-aviso-falha");
  if (avisoFalha) avisoFalha.innerHTML = "";

  // 1. Verifica eleitor autenticado
  const eleitor = appState.eleitorFase4 || appState.usuarioAtual;
  if (!eleitor || !eleitor.identificador) {
    showToast(
      "Eleitor Não Identificado",
      "Por favor, identifique seu SARAM ou CPF antes de registrar o voto.",
      "warning",
      5000
    );
    if (avisoFalha) {
      avisoFalha.innerHTML = `
        <div class="alert alert-warning" style="text-align: left; margin-top: 0.5rem;">
          <span>⚠️</span>
          <div><strong>Identificação Pendente:</strong> Clique em "Trocar Eleitor" no painel superior e digite seu SARAM ou CPF.</div>
        </div>
      `;
    }
    toggleTrocarEleitorFase4(true);
    return;
  }

  // 2. Valida se as 3 classes obrigatórias foram selecionadas
  const categoriasObrigatorias = [
    { id: "Graduados", nome: "Graduado Padrão (SO / SGT)" },
    { id: "Pracas", nome: "Praça Padrão (SD / CB)" },
    { id: "Civil", nome: "Civil Padrão (SPPF / SPTF)" }
  ];

  const faltantes = categoriasObrigatorias.filter(c => !appState.votosFase4[c.id]);

  if (faltantes.length > 0) {
    // Aplica animação pulsante de destaque nos blocos não preenchidos
    faltantes.forEach(f => {
      const box = document.getElementById(`categoria-box-${f.id}`);
      if (box) {
        box.classList.remove("missing-category-pulse");
        void box.offsetWidth; // Força reflow para reiniciar animação
        box.classList.add("missing-category-pulse");
      }
    });

    // Rola a tela suavemente até a primeira categoria pendente
    const primeiroFaltante = document.getElementById(`categoria-box-${faltantes[0].id}`);
    if (primeiroFaltante) {
      primeiroFaltante.scrollIntoView({ behavior: "smooth", block: "center" });
    }

    const nomesFaltantes = faltantes.map(f => `<strong>${escapeHtml(f.nome)}</strong>`).join(", ");

    // Aviso em Toast explicativo do motivo do bloqueio do clique
    showToast(
      "Seleção Incompleta!",
      `O voto não pôde ser gravado: você precisa escolher 1 candidato para: ${faltantes.map(f => f.nome).join(", ")}. Clique no cartão desejado.`,
      "warning",
      6500
    );

    // Aviso inline explícito logo abaixo do botão para total transparência
    if (avisoFalha) {
      avisoFalha.innerHTML = `
        <div class="alert alert-warning" style="text-align: left; margin-top: 0.5rem;">
          <span style="font-size: 1.4rem;">⚠️</span>
          <div>
            <strong>O botão de gravação não pode prosseguir:</strong><br>
            Você ainda não escolheu seu candidato em: ${nomesFaltantes}.<br>
            <em style="font-size: 0.82rem; color: #78350f;">(Pelo regulamento oficial da COMARA, é obrigatório votar em 1 representante por classe. Não há voto em branco nem nulo. Clique em um candidato acima).</em>
          </div>
        </div>
      `;
    }

    return; // Interrompe o envio
  }

  // 3. Diálogo de confirmação com resumo das escolhas
  const candGrad = (appState.cedulaCandidatos.Graduados || []).find(c => c.id === appState.votosFase4.Graduados);
  const candPrac = (appState.cedulaCandidatos.Pracas || []).find(c => c.id === appState.votosFase4.Pracas);
  const candCiv = (appState.cedulaCandidatos.Civil || []).find(c => c.id === appState.votosFase4.Civil);

  const resumo = 
    `Confirma a gravação definitiva do seu voto?\n\n` +
    `⭐ Graduado: ${candGrad ? candGrad.posto_grad_cargo + ' ' + candGrad.nome_guerra : '#' + appState.votosFase4.Graduados}\n` +
    `🎖️ Praça: ${candPrac ? candPrac.posto_grad_cargo + ' ' + candPrac.nome_guerra : '#' + appState.votosFase4.Pracas}\n` +
    `🏛️ Civil: ${candCiv ? candCiv.posto_grad_cargo + ' ' + candCiv.nome_guerra : '#' + appState.votosFase4.Civil}\n\n` +
    `Esta ação é confidencial, criptografada e definitiva.`;

  if (!confirm(resumo)) {
    return;
  }

  const btnGravar = document.getElementById("btn-gravar-voto");
  if (btnGravar) {
    btnGravar.disabled = true;
    btnGravar.innerHTML = `<span>⏳</span> Criptografando e Gravando Voto...`;
  }

  try {
    const res = await fetch("/api/fase4/votar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        identificador: eleitor.identificador,
        votos: appState.votosFase4
      })
    });
    const data = await res.json();

    if (!res.ok) {
      throw new Error(data.detail || "Erro ao gravar voto.");
    }

    // Sucesso
    showToast(
      "Voto Registrado com Sucesso!",
      "Sua escolha foi gravada com integridade inviolável e criptografia SHA-256.",
      "success",
      6000
    );

    document.getElementById("fase4-comprovante-hash").textContent = data.comprovante_hash;
    document.getElementById("fase4-comprovante-data").textContent = `Data/Hora do Registro: ${new Date(data.data_hora).toLocaleString('pt-BR')}`;

    document.getElementById("fase4-box-cedula").style.display = "none";
    document.getElementById("fase4-box-comprovante").style.display = "block";

  } catch (err) {
    showToast("Não Foi Possível Votar", err.message, "error", 7000);
    if (avisoFalha) {
      avisoFalha.innerHTML = `
        <div class="alert alert-danger" style="text-align: left; margin-top: 0.5rem;">
          <span>⛔</span>
          <div>
            <strong>Falha ao Processar Voto:</strong> ${escapeHtml(err.message)}<br>
            <em style="font-size: 0.82rem;">Caso este eleitor já tenha votado nesta eleição, novos votos são bloqueados automaticamente.</em>
          </div>
        </div>
      `;
    }
  } finally {
    if (btnGravar) {
      btnGravar.disabled = false;
      btnGravar.innerHTML = `<span>🔒</span> Gravar Voto Definitivo`;
    }
  }
}

function resetCabineVotacaoFase4() {
  appState.votosFase4 = { Graduados: null, Pracas: null, Civil: null };
  const inputSaram = document.getElementById("fase4-input-saram");
  if (inputSaram) inputSaram.value = "";
  const feedback = document.getElementById("fase4-auth-feedback");
  if (feedback) feedback.innerHTML = "";
  const avisoFalha = document.getElementById("fase4-voto-aviso-falha");
  if (avisoFalha) avisoFalha.innerHTML = "";

  document.getElementById("fase4-box-cedula").style.display = "block";
  document.getElementById("fase4-box-comprovante").style.display = "none";

  renderizarCartoesCedulaClique("Graduados", "cedula-fase4-graduados", "badge-graduados");
  renderizarCartoesCedulaClique("Pracas", "cedula-fase4-pracas", "badge-pracas");
  renderizarCartoesCedulaClique("Civil", "cedula-fase4-civil", "badge-civil");
  atualizarPillsProgressoFase4();

  toggleTrocarEleitorFase4(true);
  showToast("Cabine Liberada", "Informe o SARAM ou CPF do próximo votante.", "info");
}

// ==========================================
// ABA 6: FASE 5 - DECISÃO DO PRESIDENTE DA COMARA
// ==========================================
async function carregarFase5() {
  const container = document.getElementById("container-fase5-decisoes");
  const badgeGeral = document.getElementById("fase5-status-geral-badge");
  if (!container) return;

  container.innerHTML = `<div style="text-align:center; padding: 2rem; color: var(--text-muted);">Consultando apuração e decisões da Presidência da COMARA...</div>`;

  try {
    const res = await fetch("/api/fase5/resultado-eleicao");
    if (!res.ok) throw new Error("Erro ao obter resultado da Fase 5.");
    const data = await res.json();

    if (badgeGeral) {
      badgeGeral.innerHTML = data.concluido
        ? `<span class="badge badge-homologado" style="background:#dcfce7; color:#15803d; font-size:0.85rem;">🏆 Processo Homologado pela Presidência</span>`
        : `<span class="badge badge-warning" style="font-size:0.85rem;">⏳ Deliberação em Andamento (${data.total_votantes} eleitores votaram)</span>`;
    }

    const podeDecidir = (appState.usuarioAtual && (appState.usuarioAtual.papel === "CMDT_OM" || appState.usuarioAtual.papel === "ADMINISTRADOR"));

    let html = "";
    for (const catId of ["Graduados", "Pracas", "Civil"]) {
      const catData = data.resultado_por_categoria[catId];
      if (!catData) continue;

      const maisVotado = catData.mais_votado;
      const decisao = catData.decisao_comando;
      const candidatos = catData.candidatos || [];

      html += `
        <div class="card" style="margin-bottom: 2rem; border-left: 5px solid var(--accent-gold);">
          <div class="card-header">
            <div>
              <h3 class="card-title" style="font-size: 1.15rem;">👑 ${catData.classe_nome}</h3>
              <p class="card-subtitle">Apuração Geral da Fase 4 &bull; ${candidatos.length} concorrentes</p>
            </div>
            ${decisao ? '<span class="badge badge-homologado">DECISÃO FORMALIZADA</span>' : '<span class="badge badge-warning">AGUARDANDO DECISÃO</span>'}
          </div>
      `;

      // Tabela de Apuração da Classe
      html += `
        <div class="table-responsive" style="margin-bottom: 1.25rem;">
          <table class="data-table">
            <thead>
              <tr>
                <th style="width: 70px;">Classif.</th>
                <th>Posto/Grad</th>
                <th>Nome de Guerra</th>
                <th>Divisão</th>
                <th style="text-align: center;">Total de Votos (Fase 4)</th>
                <th>Tempo COMARA (Critério Desempate)</th>
              </tr>
            </thead>
            <tbody>
      `;

      if (candidatos.length === 0) {
        html += `<tr><td colspan="6" style="text-align: center; color: var(--text-muted);">Nenhum voto registrado para esta classe na Fase 4.</td></tr>`;
      } else {
        candidatos.forEach((c, idx) => {
          const isTop1 = (idx === 0);
          html += `
            <tr style="${isTop1 ? 'background: #fefce8; font-weight: 600;' : ''}">
              <td style="text-align: center;">
                ${isTop1 ? '🥇 1º' : `${idx + 1}º`}
              </td>
              <td>${escapeHtml(c.posto_grad_cargo)}</td>
              <td><strong>${escapeHtml(c.nome_guerra)}</strong></td>
              <td>${escapeHtml(c.divisao)}</td>
              <td style="text-align: center;"><span class="badge badge-graduados" style="font-size:0.9rem;">${c.total_votos || 0} votos</span></td>
              <td>${c.tempo_comara_meses} meses</td>
            </tr>
          `;
        });
      }

      html += `
            </tbody>
          </table>
        </div>
      `;

      // Bloco de Decisão Formalizada ou Formulário de Decisão do Comandante
      if (decisao) {
        const isHomologado = decisao.acao_comando === "HOMOLOGADO_ELEITO";
        html += `
          <div style="background: #f8fafc; border: 2px solid ${isHomologado ? '#10b981' : '#f59e0b'}; border-radius: var(--radius); padding: 1.25rem;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
              <div style="font-size: 1.1rem; font-weight: 800; color: var(--primary-navy);">
                ${isHomologado ? '✅ HOMOLOGAÇÃO DO RESULTADO POPULAR' : '⚖️ PRERROGATIVA DO COMANDO: INDICAÇÃO DIRETA'}
              </div>
              <span class="badge ${isHomologado ? 'badge-homologado' : 'badge-warning'}">${decisao.acao_comando}</span>
            </div>

            <p style="font-size: 0.95rem; margin-bottom: 0.5rem;">
              <strong>Ganhador Oficial:</strong> ${escapeHtml(decisao.vencedor_posto)} ${escapeHtml(decisao.vencedor_nome_guerra)}
            </p>
            <p style="font-size: 0.88rem; color: var(--text-secondary); margin-bottom: 0.75rem;">
              <strong>Despacho do Presidente da COMARA:</strong> "${escapeHtml(decisao.despacho || 'Sem despacho adicional.')}"
            </p>
            <div style="font-size: 0.78rem; color: var(--text-muted); border-top: 1px dashed var(--border-color); padding-top: 0.5rem; display: flex; justify-content: space-between; flex-wrap: wrap;">
              <span>Assinado por: <strong>${escapeHtml(decisao.comandante_nome)}</strong> (${escapeHtml(decisao.comandante_saram)})</span>
              <span>Assinatura Digital SHA-256: <code>${escapeHtml(decisao.assinatura_digital_hash ? decisao.assinatura_digital_hash.substring(0, 16) : '--')}...</code></span>
            </div>
          </div>
        `;
      } else if (podeDecidir && maisVotado) {
        html += `
          <div style="background: #fffbeb; border: 1px solid #fde68a; border-radius: var(--radius); padding: 1.25rem;">
            <h4 style="color: var(--primary-navy); margin-bottom: 0.75rem; font-size: 1rem;">
              ⚖️ Painel de Decisão do Presidente da COMARA / Comandante da OM (${catData.classe_nome})
            </h4>

            <form onsubmit="handleSalvarDecisaoComandante(event, '${catId}', ${maisVotado.id})">
              <div class="form-group" style="margin-bottom: 1rem;">
                <label style="font-weight: 700; display: block; margin-bottom: 0.5rem;">Escolha da Presidência:</label>
                <div style="display: flex; gap: 1.5rem; flex-wrap: wrap;">
                  <label style="display: flex; align-items: center; gap: 0.5rem; cursor: pointer;">
                    <input type="radio" name="acao_comando_${catId}" value="HOMOLOGADO_ELEITO" checked onchange="toggleIndicarDireto('${catId}', false)">
                    <span><strong>A Favor:</strong> Homologar o mais votado (<strong>${escapeHtml(maisVotado.posto_grad_cargo)} ${escapeHtml(maisVotado.nome_guerra)}</strong>)</span>
                  </label>
                  <label style="display: flex; align-items: center; gap: 0.5rem; cursor: pointer;">
                    <input type="radio" name="acao_comando_${catId}" value="INDICADO_DIRETO_CMDT" onchange="toggleIndicarDireto('${catId}', true)">
                    <span><strong>Contra:</strong> Usar prerrogativa de Comandante e indicar outro ganhador</span>
                  </label>
                </div>
              </div>

              <div id="box-outro-ganhador-${catId}" class="form-group" style="display: none; margin-bottom: 1rem; background: #fff; padding: 0.75rem; border-radius: var(--radius); border: 1px solid var(--border-color);">
                <label class="form-label" for="select-ganhador-direto-${catId}">Selecione quem será o Ganhador Designado pela Presidência:</label>
                <select id="select-ganhador-direto-${catId}" class="form-control">
                  ${candidatos.map(c => `
                    <option value="${c.id}">${escapeHtml(c.posto_grad_cargo)} ${escapeHtml(c.nome_guerra)} (${escapeHtml(c.divisao)})</option>
                  `).join("")}
                </select>
              </div>

              <div class="form-group" style="margin-bottom: 1rem;">
                <label class="form-label" for="despacho-cmdt-${catId}">Despacho Fundamentado do Comandante:</label>
                <textarea id="despacho-cmdt-${catId}" class="form-control" rows="2" placeholder="Justificativa formal institucional da homologação ou indicação direta..."></textarea>
              </div>

              <button type="submit" class="btn btn-gold">
                <span>✍️</span> Formalizar Decisão da Presidência (${catData.classe_nome})
              </button>
            </form>
          </div>
        `;
      } else {
        html += `
          <div class="alert alert-info">
            <span>ℹ️</span>
            <div>Aguardando encerramento da votação geral e acesso do Presidente da COMARA para deliberação final.</div>
          </div>
        `;
      }

      html += `</div>`;
    }

    container.innerHTML = html;
  } catch (err) {
    container.innerHTML = `<div class="alert alert-danger"><span>⚠️</span> <div>Falha: ${err.message}</div></div>`;
  }
}

window.toggleIndicarDireto = function(catId, mostrar) {
  const box = document.getElementById(`box-outro-ganhador-${catId}`);
  if (box) box.style.display = mostrar ? "block" : "none";
};

window.handleSalvarDecisaoComandante = async function(e, categoria, maisVotadoId) {
  e.preventDefault();
  if (!appState.usuarioAtual || (appState.usuarioAtual.papel !== "CMDT_OM" && appState.usuarioAtual.papel !== "ADMINISTRADOR")) {
    showToast("Acesso Restrito ao Comando", "Apenas o Presidente da COMARA (Comandante da OM) tem autoridade para homologar a Fase 5.", "warning", 6000);
    return;
  }

  const acao = document.querySelector(`input[name="acao_comando_${categoria}"]:checked`).value;
  let candidatoFinalId = maisVotadoId;

  if (acao === "INDICADO_DIRETO_CMDT") {
    const sel = document.getElementById(`select-ganhador-direto-${categoria}`);
    candidatoFinalId = parseInt(sel.value, 10);
  }

  const despacho = document.getElementById(`despacho-cmdt-${categoria}`).value.trim();

  if (!confirm(`Confirma a formalização da decisão do Presidente da COMARA para a classe ${categoria}?`)) {
    return;
  }

  try {
    const res = await fetch("/api/fase5/decisao-comandante", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        categoria: categoria,
        candidato_mais_votado_id: maisVotadoId,
        candidato_final_id: candidatoFinalId,
        acao_comando: acao,
        despacho: despacho || "Homologado conforme normas regulamentares da COMARA.",
        comandante_nome: appState.usuarioAtual ? appState.usuarioAtual.nome_completo : "Cel Av Trigueiro",
        comandante_saram: appState.usuarioAtual ? appState.usuarioAtual.identificador : "1111111",
        ldap_username: appState.usuarioAtual ? appState.usuarioAtual.ldap_username : "trigueiro.cmdt"
      })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Erro ao salvar decisão da Presidência.");

    showToast("Decisão Homologada com Sucesso!", data.mensagem, "success", 6000);
    carregarFase5();
    carregarStatusFases();
  } catch (err) {
    showToast("Falha na Decisão Presidencial", err.message, "error", 6000);
  }
};

// ==========================================
// ABA 7: AUDITORIA & TESTES
// ==========================================
function initEventosAuditoria() {
  const btnTestes = document.getElementById("btn-executar-testes");
  if (btnTestes) {
    btnTestes.addEventListener("click", handleExecutarTestes);
  }

  const btnLogs = document.getElementById("btn-atualizar-logs");
  if (btnLogs) {
    btnLogs.addEventListener("click", carregarLogsAuditoria);
  }
}

async function handleExecutarTestes() {
  const container = document.getElementById("resultado-testes-container");
  const btn = document.getElementById("btn-executar-testes");
  btn.disabled = true;
  btn.innerHTML = "<span>⏳</span> Executando testes...";
  container.innerHTML = `<div class="alert alert-info">Executando suíte de testes de integridade das 5 fases...</div>`;

  try {
    const res = await fetch("/api/testes/executar", { method: "POST" });
    const data = await res.json();

    const isSuccess = data.sucesso;
    container.innerHTML = `
      <div class="alert ${isSuccess ? 'alert-success' : 'alert-danger'}" style="margin-bottom: 1rem;">
        <span style="font-size: 1.5rem;">${isSuccess ? '✅' : '❌'}</span>
        <div>
          <strong>${isSuccess ? 'TODOS OS TESTES PASSARAM COM SUCESSO!' : 'FALHA NOS TESTES'}</strong><br>
          Total: ${data.total_testes} testes | Erros: ${data.erros} | Falhas: ${data.falhas} | Duração: ${data.tempo_execucao}s
        </div>
      </div>
      <div style="background: #1e293b; color: #f8fafc; padding: 0.9rem; border-radius: var(--radius); font-family: monospace; font-size: 0.78rem; max-height: 250px; overflow-y: auto;">
        ${escapeHtml(data.saida || "Execução concluída sem mensagens.")}
      </div>
    `;
    showToast(isSuccess ? "Suíte de Testes Aprovada!" : "Falha nos Testes", `Total: ${data.total_testes} testes | Erros: ${data.erros} | Falhas: ${data.falhas}`, isSuccess ? "success" : "error", 5000);
    carregarLogsAuditoria();
  } catch (err) {
    container.innerHTML = `<div class="alert alert-danger"><span>⚠️</span> <div>Falha ao executar testes: ${err.message}</div></div>`;
    showToast("Erro ao Executar Testes", err.message, "error", 5000);
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<span>▶️</span> Executar Suíte de Testes`;
  }
}

async function carregarLogsAuditoria() {
  const corpo = document.getElementById("tabela-logs-corpo");
  if (!corpo) return;

  corpo.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-muted);">Consultando logs de auditoria...</td></tr>`;

  try {
    const res = await fetch("/api/auditoria/logs?limite=50");
    if (!res.ok) throw new Error("Erro ao consultar logs de auditoria.");
    const logs = await res.json();

    if (logs.length === 0) {
      corpo.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-muted);">Nenhum log gravado até o momento.</td></tr>`;
      return;
    }

    corpo.innerHTML = logs.map(l => `
      <tr>
        <td style="font-size: 0.75rem; white-space: nowrap;">${new Date(l.timestamp).toLocaleString('pt-BR')}</td>
        <td><code>${escapeHtml(l.acao)}</code></td>
        <td><strong>${escapeHtml(l.usuario || 'SISTEMA')}</strong></td>
        <td>${escapeHtml(l.divisao || '-')}</td>
        <td style="font-size: 0.8rem;">${escapeHtml(l.detalhes)}</td>
        <td><code title="${escapeHtml(l.hash_sha256)}">${escapeHtml(l.hash_sha256 ? l.hash_sha256.substring(0, 10) + '...' : '-')}</code></td>
      </tr>
    `).join("");
  } catch (err) {
    corpo.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--danger);">Falha: ${err.message}</td></tr>`;
  }
}

// ==========================================
// UTILITÁRIOS
// ==========================================
function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
