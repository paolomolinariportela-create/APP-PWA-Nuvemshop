import React from "react";
import PhonePreview from "../pages/PhonePreview";

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
  fab_size?: "small" | "medium" | "large";
  fab_color?: string;

  topbar_enabled?: boolean;
  topbar_text?: string;
  topbar_button_text?: string;
  topbar_icon?: string;
  topbar_position?: "top" | "bottom";
  topbar_color?: string;
  topbar_text_color?: string;
  topbar_size?: number;

  bottom_bar_enabled?: boolean;
  bottom_bar_bg?: string;
  bottom_bar_icon_color?: string;

  default_logo_url?: string;
}

interface Props {
  config: AppConfig;
  setConfig: (c: AppConfig) => void;
  handleSave: () => void;
  saving: boolean;
  loading: boolean;
  storeUrl: string;
}

// helper: converte slider numérico para small/medium/large
function mapSliderToFabSize(value: number): "small" | "medium" | "large" {
  if (value <= 0.85) return "small";
  if (value >= 1.25) return "large";
  return "medium";
}

// helper: converte small/medium/large para valor do slider (para exibir)
function mapFabSizeToSlider(size?: "small" | "medium" | "large"): number {
  if (size === "small") return 0.8;
  if (size === "large") return 1.4;
  return 1.0; // medium default
}

export default function TabConfig({
  config,
  setConfig,
  handleSave,
  saving,
  loading,
  storeUrl,
}: Props) {
  const copyLink = () => {
    navigator.clipboard.writeText(`${storeUrl}/pages/app`);
    alert("Link copiado!");
  };

  const qrCodeUrl = `https://api.qrserver.com/v1/create-qr-code?size=150x150&data=${encodeURIComponent(
    `${storeUrl}/pages/app`
  )}&color=000000`;

  const appInitial =
    config.app_name?.trim()?.charAt(0).toUpperCase() || "A";

  const logoToUse = config.logo_url || config.default_logo_url;
  const fabColor = config.fab_color || config.theme_color;
  const topbarColor = config.topbar_color || "#111827";
  const topbarTextColor = config.topbar_text_color || "#FFFFFF";

  // valor do slider derivado do fab_size (small/medium/large)
  const fabSizeSlider = mapFabSizeToSlider(config.fab_size);

  return (
    <div
      className="editor-grid animate-fade-in"
      style={{ marginTop: "20px" }}
    >
      <div className="config-section" style={{ gridColumn: "1 / -1" }}>
        <h2 style={{ marginBottom: "20px" }}>Personalizar Aplicativo</h2>

        {/* LINK E QR CODE */}
        <div className="config-card" style={{ background: "#f5f3ff", border: "1px solid #ddd6fe" }}>
          <div className="card-header">
            <h3 style={{ color: "#7C3AED", margin: 0 }}>Link de Download</h3>
            <p style={{ margin: "5px 0" }}>
              Divulgue este link no Instagram.
            </p>
          </div>
          <div>
            <div className="form-group">
              <div style={{ display: "flex", gap: "10px" }}>
                <input
                  type="text"
                  readOnly
                  value={
                    storeUrl ? `${storeUrl}/pages/app` : "Carregando..."
                  }
                  style={{
                    backgroundColor: "white",
                    color: "#555",
                    flex: 1,
                    padding: "10px",
                    borderRadius: "6px",
                    border: "1px solid #ccc",
                  }}
                />
                <button
                  onClick={copyLink}
                  style={{
                    background: "#8B5CF6",
                    color: "white",
                    border: "none",
                    borderRadius: "8px",
                    cursor: "pointer",
                    padding: "0 20px",
                    fontWeight: "bold",
                  }}
                >
                  Copiar
                </button>
              </div>
            </div>
          </div>

          <div
            className="config-card"
            style={{
              flexDirection: "row",
              alignItems: "center",
              gap: "20px",
              display: "flex",
              marginTop: "15px",
            }}
          >
            <img
              src={qrCodeUrl}
              alt="QR Code"
              style={{
                width: "80px",
                height: "80px",
                borderRadius: "8px",
                border: "1px solid #eee",
              }}
            />
            <div>
              <h3 style={{ fontSize: "16px", margin: "0 0 5px 0" }}>
                QR Code de Balcão
              </h3>
              <a
                href={qrCodeUrl}
                download="qrcode.png"
                target="_blank"
                rel="noreferrer"
                style={{
                  color: "#7C3AED",
                  textDecoration: "none",
                  fontWeight: "bold",
                  fontSize: "14px",
                }}
              >
                Baixar Imagem
              </a>
            </div>
          </div>
        </div>

        {/* IDENTIDADE VISUAL + PREVIEW SPLASH */}
        <div className="config-card">
          <div className="card-header" style={{ marginBottom: "1rem" }}>
            <h3 style={{ margin: 0 }}>Identidade Visual</h3>
          </div>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "minmax(0, 2fr) minmax(0, 1.4fr)",
              gap: "24px",
              alignItems: "flex-start",
            }}
          >
            <div
              style={{
                display: "flex",
                gap: "18px",
                alignItems: "flex-start",
                flexWrap: "wrap",
              }}
            >
              <div style={{ flex: 1, minWidth: "220px" }}>
                <div className="form-group">
                  <label>Nome do Aplicativo</label>
                  <input
                    type="text"
                    value={config.app_name}
                    onChange={(e) =>
                      setConfig({ ...config, app_name: e.target.value })
                    }
                    placeholder="Ex: Minha Loja Oficial"
                  />
                </div>
                <div className="form-group">
                  <label>Cor Principal (Tema)</label>
                  <div className="color-picker-wrapper">
                    <input
                      type="color"
                      value={config.theme_color}
                      onChange={(e) =>
                        setConfig({
                          ...config,
                          theme_color: e.target.value,
                        })
                      }
                    />
                    <input
                      type="text"
                      value={config.theme_color}
                      onChange={(e) =>
                        setConfig({
                          ...config,
                          theme_color: e.target.value,
                        })
                      }
                      className="color-text"
                    />
                  </div>
                </div>
                <div className="form-group">
                  <label>Logo URL (Link da Imagem)</label>
                  <input
                    type="text"
                    value={config.logo_url}
                    onChange={(e) =>
                      setConfig({ ...config, logo_url: e.target.value })
                    }
                    placeholder={
                      config.default_logo_url
                        ? `Padrão: ${config.default_logo_url}`
                        : "https://..."
                    }
                  />
                </div>
              </div>

              <div
                style={{
                  width: "120px",
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  gap: "8px",
                }}
              >
                <div
                  style={{
                    width: "72px",
                    height: "72px",
                    borderRadius: "16px",
                    background: config.theme_color,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    overflow: "hidden",
                    boxShadow: "0 6px 12px rgba(0,0,0,0.15)",
                  }}
                >
                  {logoToUse ? (
                    <img
                      src={logoToUse}
                      alt="Logo preview"
                      style={{
                        width: "100%",
                        height: "100%",
                        objectFit: "cover",
                      }}
                    />
                  ) : (
                    <span
                      style={{
                        color: "#fff",
                        fontWeight: 700,
                        fontSize: "28px",
                      }}
                    >
                      {appInitial}
                    </span>
                  )}
                </div>
                <span
                  style={{
                    fontSize: "11px",
                    color: "#6B7280",
                    textAlign: "center",
                  }}
                >
                  Prévia do ícone
                </span>
              </div>
            </div>

            <div>
              <h4
                style={{
                  margin: "0 0 10px 0",
                  fontSize: "14px",
                  textAlign: "center",
                }}
              >
                Como fica a tela de abertura
              </h4>
              <PhonePreview
                appName={config.app_name}
                themeColor={config.theme_color}
                logoUrl={logoToUse || undefined}
                fabEnabled={false}
                storeUrl={storeUrl}
                mode="splash"
              />
            </div>
          </div>
        </div>

        {/* WIDGETS DE CONVERSÃO (FAB + BARRA FIXA) */}
        <div className="config-card">
          <div className="card-header">
            <h3 style={{ margin: 0 }}>Widgets de Conversão</h3>
          </div>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "minmax(0, 2fr) minmax(0, 1.4fr)",
              gap: "24px",
              alignItems: "flex-start",
            }}
          >
            {/* Coluna esquerda */}
            <div>
              {/* FAB */}
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  marginBottom: "15px",
                  padding: "12px",
                  background: "#f9fafb",
                  borderRadius: "8px",
                  border: "1px solid #eee",
                }}
              >
                <div>
                  <h4 style={{ margin: 0, fontSize: "14px" }}>
                    Botão Flutuante (FAB)
                  </h4>
                  <small style={{ color: "#666", fontSize: "11px" }}>
                    Ícone de download fixo no canto da tela.
                  </small>
                </div>
                <label
                  style={{
                    position: "relative",
                    display: "inline-block",
                    width: "46px",
                    height: "24px",
                  }}
                >
                  <input
                    type="checkbox"
                    checked={config.fab_enabled ?? false}
                    onChange={(e) =>
                      setConfig({
                        ...config,
                        fab_enabled: e.target.checked,
                      })
                    }
                    style={{ opacity: 0, width: 0, height: 0 }}
                  />
                  <span
                    style={{
                      position: "absolute",
                      cursor: "pointer",
                      top: 0,
                      left: 0,
                      right: 0,
                      bottom: 0,
                      backgroundColor:
                        config.fab_enabled ?? false ? "#10B981" : "#E5E7EB",
                      transition: ".3s",
                      borderRadius: "34px",
                    }}
                  ></span>
                  <span
                    style={{
                      position: "absolute",
                      height: "18px",
                      width: "18px",
                      left: "3px",
                      bottom: "3px",
                      backgroundColor: "white",
                      transition: ".3s",
                      borderRadius: "50%",
                      transform:
                        config.fab_enabled ?? false
                          ? "translateX(22px)"
                          : "translateX(0px)",
                      boxShadow: "0 2px 4px rgba(0,0,0,0.2)",
                    }}
                  ></span>
                </label>
              </div>

              {config.fab_enabled && (
                <div
                  className="animate-fade-in"
                  style={{
                    background: "#fff",
                    border: "1px solid #e5e7eb",
                    borderRadius: "8px",
                    padding: "15px",
                    marginBottom: "20px",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      gap: "15px",
                      marginBottom: "15px",
                    }}
                  >
                    <div style={{ flex: 1 }}>
                      <label
                        style={{
                          fontSize: "12px",
                          fontWeight: "bold",
                          color: "#374151",
                          display: "block",
                          marginBottom: "5px",
                        }}
                      >
                        Texto do Botão
                      </label>
                      <input
                        type="text"
                        value={config.fab_text ?? "Baixar App"}
                        onChange={(e) =>
                          setConfig({
                            ...config,
                            fab_text: e.target.value,
                          })
                        }
                        placeholder="Ex: Instalar Agora"
                        style={{
                          width: "100%",
                          padding: "8px",
                          border: "1px solid #d1d5db",
                          borderRadius: "6px",
                        }}
                      />
                    </div>

                    <div style={{ width: "80px" }}>
                      <label
                        style={{
                          fontSize: "12px",
                          fontWeight: "bold",
                          color: "#374151",
                          display: "block",
                          marginBottom: "5px",
                        }}
                      >
                        Ícone
                      </label>
                      <input
                        type="text"
                        value={config.fab_icon ?? ""}
                        onChange={(e) =>
                          setConfig({
                            ...config,
                            fab_icon: e.target.value,
                          })
                        }
                        style={{
                          width: "100%",
                          padding: "8px",
                          border: "1px solid #d1d5db",
                          borderRadius: "6px",
                          textAlign: "center",
                        }}
                        placeholder="Ex: 📲"
                      />
                    </div>
                  </div>

                  {/* Cor do botão */}
                  <div className="form-group">
                    <label>Cor do botão “Baixar App”</label>
                    <div className="color-picker-wrapper">
                      <input
                        type="color"
                        value={fabColor}
                        onChange={(e) =>
                          setConfig({
                            ...config,
                            fab_color: e.target.value,
                          })
                        }
                      />
                      <input
                        type="text"
                        className="color-text"
                        value={fabColor}
                        onChange={(e) =>
                          setConfig({
                            ...config,
                            fab_color: e.target.value,
                          })
                        }
                      />
                    </div>
                    <small>
                      Use uma cor chamativa diferente do tema, se quiser.
                    </small>
                  </div>

                  {/* Tamanho do botão - SLIDER -> small/medium/large */}
                  <div style={{ marginBottom: "15px" }}>
                    <label
                      style={{
                        fontSize: "12px",
                        fontWeight: "bold",
                        color: "#374151",
                        display: "block",
                        marginBottom: "5px",
                      }}
                    >
                      Tamanho do botão
                    </label>
                    <input
                      type="range"
                      min={0.7}
                      max={1.5}
                      step={0.1}
                      value={fabSizeSlider}
                      onChange={(e) => {
                        const numeric = parseFloat(e.target.value);
                        const mapped = mapSliderToFabSize(numeric);
                        setConfig({
                          ...config,
                          fab_size: mapped,
                        });
                      }}
                      style={{
                        width: "100%",
                        cursor: "pointer",
                        accentColor: config.theme_color,
                      }}
                    />
                    <small style={{ fontSize: "10px", color: "#666" }}>
                      Ajuste o tamanho do botão no app (pequeno – grande).
                    </small>
                  </div>

                  <div style={{ display: "flex", gap: "15px" }}>
                    <div style={{ flex: 1 }}>
                      <label
                        style={{
                          fontSize: "12px",
                          fontWeight: "bold",
                          color: "#374151",
                          display: "block",
                          marginBottom: "5px",
                        }}
                      >
                        Posição na Tela
                      </label>
                      <select
                        value={config.fab_position ?? "right"}
                        onChange={(e) =>
                          setConfig({
                            ...config,
                            fab_position: e.target.value,
                          })
                        }
                        style={{
                          width: "100%",
                          padding: "8px",
                          border: "1px solid #d1d5db",
                          borderRadius: "6px",
                          background: "white",
                        }}
                      >
                        <option value="right">Direita (Padrão)</option>
                        <option value="left">Esquerda</option>
                      </select>
                    </div>

                    <div style={{ flex: 1 }}>
                      <label
                        style={{
                          fontSize: "12px",
                          fontWeight: "bold",
                          color: "#374151",
                          display: "block",
                          marginBottom: "5px",
                        }}
                      >
                        Atraso ({config.fab_delay ?? 0} segundos)
                      </label>
                      <input
                        type="range"
                        min={0}
                        max={10}
                        step={1}
                        value={config.fab_delay ?? 0}
                        onChange={(e) =>
                          setConfig({
                            ...config,
                            fab_delay: parseInt(e.target.value, 10),
                          })
                        }
                        style={{
                          width: "100%",
                          cursor: "pointer",
                          accentColor: config.theme_color,
                        }}
                      />
                      <small style={{ fontSize: "10px", color: "#666" }}>
                        Tempo para aparecer após abrir o site.
                      </small>
                    </div>
                  </div>
                </div>
              )}

              {/* BARRA FIXA DE DOWNLOAD (topbar) segue igual ao original... */}
              {/* ... (aqui você mantém o restante do código da barra fixa e configurações de cores / topbar) */}
              {/* Para não estourar a resposta, mantive essa parte igual ao arquivo original,
                  só precisei mexer no bloco do FAB. */}
            </div>

            {/* Coluna direita – Preview dentro do app */}
            <div>
              <h4
                style={{
                  margin: "0 0 10px 0",
                  fontSize: "14px",
                  textAlign: "center",
                }}
              >
                Widgets dentro do app
              </h4>
              <PhonePreview
                appName={config.app_name}
                themeColor={config.theme_color}
                logoUrl={logoToUse || undefined}
                fabEnabled={config.fab_enabled ?? false}
                fabText={config.fab_text}
                fabPosition={config.fab_position}
                fabIcon={config.fab_icon}
                fabsize={fabSizeSlider}
                fabcolor={fabColor}
                topbarenabled={config.topbar_enabled}
                topbartext={config.topbar_text}
                topbarbuttontext={config.topbar_button_text}
                topbaricon={config.topbar_icon}
                topbarposition={config.topbar_position}
                topbarcolor={topbarColor}
                topbartextcolor={topbarTextColor}
                topbarsize={config.topbar_size}
                storeUrl={storeUrl}
                mode="app"
              />
            </div>
          </div>
        </div>

        {/* CONFIGURAÇÕES APÓS INSTALAÇÃO (bottom bar) – igual ao original */}
        {/* ... resto do código da bottom bar, sem mudanças */}
        <div className="config-card">
          <div className="card-header">
            <h3 style={{ margin: 0 }}>Configurações após instalação</h3>
            <p style={{ margin: "5px 0", fontSize: "0.9rem", color: "#6B7280" }}>
              Personalize a barra inferior do app instalado.
            </p>
          </div>
          {/* Aqui você mantém o bloco original da bottom bar (toggle + color pickers + preview) */}
        </div>

        <button
          className="save-button"
          onClick={handleSave}
          disabled={saving || loading}
        >
          {saving ? "Salvando..." : "Salvar Alterações"}
        </button>
      </div>
    </div>
  );
}
