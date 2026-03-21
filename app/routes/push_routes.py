import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import "../styles/AdminPanel.css";

import TabDashboard from "../components/TabDashboard";
import TabConfig from "../components/TabConfig";
import TabCampaigns from "../components/TabCampaigns";

interface DashboardStats {
  receita: number;
  vendas: number;
  instalacoes: number;
  carrinhos_abandonados: { valor: number; qtd: number };
  taxa_conversao: { app: number; site: number };
  economia_ads: number;
  top_produtos: Array<{ nome: string; vendas: number }>;
  visualizacoes: {
    pageviews: number;
    tempo_medio: string;
    top_paginas: string[];
  };
  funil: { visitas: number; carrinho: number; checkout: number };
  recorrencia: { clientes_2x: number; taxa_recompra: number };
  ticket_medio: { app: number; site: number };
}

interface AppConfig {
  app_name: string;
  theme_color: string;
  logo_url: string;
  whatsapp_number: string;

  fab_enabled?: boolean;
  fab_text?: string;
  fab_position?: string;
  fab_icon?: string;
  fab_delay?: number;
  fab_size?: "xs" | "small" | "medium" | "large" | "xl";
  fab_color?: string;
  fab_background_image_url?: string;

  topbar_enabled?: boolean;
  topbar_text?: string;
  topbar_button_text?: string;
  topbar_icon?: string;
  topbar_position?: "top" | "bottom";
  topbar_color?: string;
  topbar_text_color?: string;
  topbar_size?: "xs" | "small" | "medium" | "large" | "xl";
  topbar_button_bg_color?: string;
  topbar_button_text_color?: string;
  topbar_background_image_url?: string;

  popup_enabled?: boolean;
  popup_image_url?: string;

  bottom_bar_enabled?: boolean;
  bottom_bar_bg?: string;
  bottom_bar_icon_color?: string;

  default_logo_url?: string;

  onesignal_app_id?: string;
  onesignal_api_key?: string;
}

// ✅ Atualizado com campos de segmentação
interface PushCampaign {
  title: string;
  message: string;
  url: string;
  filter_device?: string;
  filter_country?: string;
  send_after?: string;
}

export default function AdminPanel() {
  const [searchParams, setSearchParams] = useSearchParams();
  const tokenFromUrl = searchParams.get("token");

  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [sendingPush, setSendingPush] = useState(false);
  const [token, setToken] = useState<string | null>(
    localStorage.getItem("app_token")
  );
  const [activeTab, setActiveTab] = useState<
    "dashboard" | "campanhas" | "config" | "planos"
  >("dashboard");
  const [storeUrl, setStoreUrl] = useState("");
  const [storeLogoUrl, setStoreLogoUrl] = useState<string | null>(null);

  const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

  const [config, setConfig] = useState<AppConfig>({
    app_name: "Minha Loja",
    theme_color: "#000000",
    logo_url: "",
    whatsapp_number: "",
    fab_enabled: false,
    fab_text: "Baixar App",
    fab_position: "right",
    fab_icon: "📲",
    fab_delay: 0,
    fab_size: "medium",
    fab_color: "#000000",
    fab_background_image_url: "",
    topbar_enabled: false,
    topbar_text: "Instale o app e ganhe 10% OFF na primeira compra",
    topbar_button_text: "Instalar agora",
    topbar_icon: "📲",
    topbar_position: "top",
    topbar_color: "#111827",
    topbar_text_color: "#FFFFFF",
    topbar_size: "medium",
    topbar_button_bg_color: "#FBBF24",
    topbar_button_text_color: "#111827",
    topbar_background_image_url: "",
    popup_enabled: false,
    popup_image_url: "",
    bottom_bar_enabled: true,
    bottom_bar_bg: "#FFFFFF",
    bottom_bar_icon_color: "#6B7280",
    default_logo_url: "",
    onesignal_app_id: "",
    onesignal_api_key: "",
  });

  // ✅ Estado inicial com campos de segmentação
  const [pushForm, setPushForm] = useState<PushCampaign>({
    title: "",
    message: "",
    url: "/",
    filter_device: undefined,
    filter_country: undefined,
    send_after: undefined,
  });

  const [stats, setStats] = useState<DashboardStats>({
    receita: 0,
    vendas: 0,
    instalacoes: 0,
    carrinhos_abandonados: { valor: 0, qtd: 0 },
    taxa_conversao: { app: 0, site: 0 },
    economia_ads: 0,
    top_produtos: [],
    visualizacoes: { pageviews: 0, tempo_medio: "--", top_paginas: [] },
    funil: { visitas: 0, carrinho: 0, checkout: 0 },
    recorrencia: { clientes_2x: 0, taxa_recompra: 0 },
    ticket_medio: { app: 0, site: 0 },
  });

  useEffect(() => {
    if (tokenFromUrl) {
      localStorage.setItem("app_token", tokenFromUrl);
      setToken(tokenFromUrl);
      setSearchParams({});
    }
  }, [tokenFromUrl, setSearchParams]);

  useEffect(() => {
    if (!token) return;
    setLoading(true);

    const authFetch = (endpoint: string) =>
      fetch(`${API_URL}${endpoint}`, {
        headers: { Authorization: `Bearer ${token}` },
      });

    Promise.all([
      authFetch("/admin/config").then((r) => r.json()),
      authFetch("/analytics/dashboard").then((r) => r.json()),
      authFetch("/admin/store-info").then((r) => r.json()),
    ])
      .then(([dataConfig, dataStats, dataUrl]) => {
        const lojaLogo = dataUrl.logo_url || "";

        setConfig({
          app_name: dataConfig.app_name ?? "Minha Loja",
          theme_color: dataConfig.theme_color ?? "#000000",
          logo_url: dataConfig.logo_url ?? "",
          whatsapp_number: dataConfig.whatsapp ?? "",
          fab_enabled: dataConfig.fab_enabled ?? false,
          fab_text: dataConfig.fab_text ?? "Baixar App",
          fab_position: dataConfig.fab_position ?? "right",
          fab_icon: dataConfig.fab_icon ?? "📲",
          fab_delay: dataConfig.fab_delay ?? 0,
          fab_size: (dataConfig.fab_size as "xs" | "small" | "medium" | "large" | "xl") ?? "medium",
          fab_color: dataConfig.fab_color ?? dataConfig.theme_color ?? "#000000",
          fab_background_image_url: dataConfig.fab_background_image_url ?? "",
          topbar_enabled: dataConfig.topbar_enabled ?? false,
          topbar_text: dataConfig.topbar_text ?? "Instale o app e ganhe 10% OFF na primeira compra",
          topbar_button_text: dataConfig.topbar_button_text ?? "Instalar agora",
          topbar_icon: dataConfig.topbar_icon ?? "📲",
          topbar_position: dataConfig.topbar_position ?? "top",
          topbar_color: dataConfig.topbar_color ?? "#111827",
          topbar_text_color: dataConfig.topbar_text_color ?? "#FFFFFF",
          topbar_size: (dataConfig.topbar_size as "xs" | "small" | "medium" | "large" | "xl") ?? "medium",
          topbar_button_bg_color: dataConfig.topbar_button_bg_color ?? "#FBBF24",
          topbar_button_text_color: dataConfig.topbar_button_text_color ?? "#111827",
          topbar_background_image_url: dataConfig.topbar_background_image_url ?? "",
          popup_enabled: dataConfig.popup_enabled ?? false,
          popup_image_url: dataConfig.popup_image_url ?? "",
          bottom_bar_enabled: dataConfig.bottom_bar_enabled ?? true,
          bottom_bar_bg: dataConfig.bottom_bar_bg ?? "#FFFFFF",
          bottom_bar_icon_color: dataConfig.bottom_bar_icon_color ?? "#6B7280",
          default_logo_url: lojaLogo,
          onesignal_app_id: dataConfig.onesignal_app_id ?? "",
          onesignal_api_key: dataConfig.onesignal_api_key ?? "",
        });

        setStats(dataStats);
        setStoreUrl(dataUrl.url);
        setStoreLogoUrl(lojaLogo);
      })
      .catch((err) => {
        console.error(err);
        // @ts-ignore
        if (err.status === 401) {
          localStorage.removeItem("app_token");
          setToken(null);
        }
      })
      .finally(() => setLoading(false));
  }, [token, API_URL]);

  const handleSave = async () => {
    if (!token) return;
    setSaving(true);
    try {
      const { default_logo_url, ...payload } = config;
      await fetch(`${API_URL}/admin/config`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
      });
      alert("✨ Salvo!");
    } catch (error) {
      alert("Erro ao salvar.");
    } finally {
      setSaving(false);
    }
  };

  const handleSendPush = async () => {
    if (!token) return;
    if (!pushForm.title || !pushForm.message) {
      alert("Preencha tudo!");
      return;
    }

    const confirmMsg = pushForm.send_after
      ? `Agendar notificação para ${new Date(pushForm.send_after).toLocaleString('pt-BR')}?`
      : "Enviar notificação agora?";
    if (!confirm(confirmMsg)) return;

    setSendingPush(true);
    try {
      const res = await fetch(`${API_URL}/push/send`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(pushForm),
      });
      const data = await res.json();
      if (data.status === "success") {
        const msg = data.scheduled
          ? `⏰ Agendado com sucesso!`
          : `✅ Enviado para ${data.sent} pessoas.`;
        alert(msg);
        // ✅ Reseta form incluindo filtros de segmentação
        setPushForm({
          title: "",
          message: "",
          url: "/",
          filter_device: undefined,
          filter_country: undefined,
          send_after: undefined,
        });
      } else {
        alert(`⚠️ Erro: ${JSON.stringify(data.detail || data.message)}`);
      }
    } catch (e) {
      alert("Erro de conexão.");
    } finally {
      setSendingPush(false);
    }
  };

  if (!token)
    return <div className="error-screen">🔒 Login necessário.</div>;

  return (
    <div className="dashboard-container">
      <header className="dashboard-header">
        <div className="header-left">
          <div className="logo-area">
            <h1>App Builder</h1>
            <span className="badge-pro">PRO</span>
          </div>

          <nav className="header-nav">
            <button className={activeTab === "dashboard" ? "nav-link active" : "nav-link"} onClick={() => setActiveTab("dashboard")}>
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 13h8V3H3v10zm10 8h8V11h-8v10zM3 21h8v-6H3v6zm10-18v6h8V3h-8z" fill="currentColor" /></svg>
              <span>Dashboard</span>
            </button>

            <button className={activeTab === "campanhas" ? "nav-link active" : "nav-link"} onClick={() => setActiveTab("campanhas")}>
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 10v4h2l5 5V5L5 10H3zm13-1c1.66 0 3 1.34 3 3 0 1.65-1.34 3-3 3v-2a1 1 0 0 0 0-2V9zM17 5a7 7 0 0 1 0 14v-2a5 5 0 0 0 0-10V5z" fill="currentColor" /></svg>
              <span>Campanhas</span>
            </button>

            <button className={activeTab === "config" ? "nav-link active" : "nav-link"} onClick={() => setActiveTab("config")}>
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M19.14 12.94c.04-.31.06-.63.06-.94s-.02-.63-.06-.94l2.03-1.58a.5.5 0 0 0 .11-.64l-1.92-3.32a.5.5 0 0 0-.61-.22L16.9 5.5a7.07 7.07 0 0 0-1.63-.94L15 2.5a.5.5 0 0 0-.5-.5h-5a.5.5 0 0 0-.5.5l-.27 2.06c-.6.24-1.15.55-1.66.92L4.25 4.3a.5.5 0 0 0-.61.22L1.72 7.84a.5.5 0 0 0 .11.64l2.03 1.58c-.04.31-.06.64-.06.94s.02.63.06.94L1.83 13.5a.5.5 0 0 0-.11.64l1.92 3.32c.14.24.44.34.7.22l2.3-1.06c.51.37 1.06.68 1.66.92L9 21.5a.5.5 0 0 0 .5.5h5a.5.5 0 0 0 .5-.5l.27-2.06c.6-.24 1.15-.55 1.66-.92l2.3 1.06c.26.12.56.02.7-.22l1.92-3.32a.5.5 0 0 0-.11-.64l-2.03-1.58zM12 15a3 3 0 1 1 0-6 3 3 0 0 1 0 6z" fill="currentColor" /></svg>
              <span>Configurações</span>
            </button>

            <button className={activeTab === "planos" ? "nav-link active" : "nav-link"} onClick={() => setActiveTab("planos")}>
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2 3 5v6c0 5 3.8 9.7 9 11 5.2-1.3 9-6 9-11V5l-9-3zm0 2.2L18.5 6 12 8.8 5.5 6 12 4.2zM5 9.3l6 2.6v8.3C7.9 18.9 5 15.3 5 11.6v-2.3zm8 11.9v-8.3l6-2.6v2.3c0 3.7-2.9 7.3-6 8.6z" fill="currentColor" /></svg>
              <span>Planos</span>
            </button>

            <button className="nav-link" onClick={() => window.open(storeUrl, "_blank")}>
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 10V4h16v6l-2 10H6L4 10zm4 8h8v-4H8v4zm0-6h8V6H8v6z" fill="currentColor" /></svg>
              <span>Ver loja</span>
            </button>
          </nav>
        </div>

        <div className="header-right">
          <div className="status-indicator">
            <span className="dot online"></span>
            <span>Online</span>
          </div>
        </div>
      </header>

      <main className="dashboard-content">
        {activeTab === "dashboard" && <TabDashboard stats={stats} />}

        {activeTab === "config" && (
          <TabConfig
            config={config}
            setConfig={setConfig}
            handleSave={handleSave}
            saving={saving}
            loading={loading}
            storeUrl={storeUrl}
          />
        )}

        {activeTab === "campanhas" && (
          <TabCampaigns
            stats={stats}
            pushForm={pushForm}
            setPushForm={setPushForm}
            handleSendPush={handleSendPush}
            sendingPush={sendingPush}
            token={token}
            API_URL={API_URL}
          />
        )}

        {activeTab === "planos" && (
          <div className="plans-container" style={{ textAlign: "center", padding: "40px" }}>
            <h2>Planos</h2>
            <p>Em breve...</p>
          </div>
        )}
      </main>
    </div>
  );
}
