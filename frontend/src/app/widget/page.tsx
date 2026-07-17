import ChatWidget from "@/components/chat-widget";

type WidgetPageProps = {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

function first(value: string | string[] | undefined) {
  return Array.isArray(value) ? value[0] : value;
}

function exactOrigin(value: string | undefined) {
  if (!value) return undefined;
  try {
    const parsed = new URL(value);
    return parsed.protocol === "http:" || parsed.protocol === "https:" ? parsed.origin : undefined;
  } catch {
    return undefined;
  }
}

export default async function WidgetPage({ searchParams }: WidgetPageProps) {
  const params = await searchParams;
  const locale = first(params.locale) === "en" ? "en" : "es";
  const apiUrl = exactOrigin(process.env.NEXT_PUBLIC_CHAT_API_URL) ?? "http://localhost:8000";
  const parentOrigin = exactOrigin(first(params.parentOrigin));
  const noticeVersion = process.env.PRIVACY_NOTICE_VERSION ?? "development-placeholder-v0";
  const privacyNotice = {
    es:
      process.env.PRIVACY_NOTICE_ES ??
      "Aviso de desarrollo: no compartas datos personales. Configura el aviso aprobado antes de producción.",
    en:
      process.env.PRIVACY_NOTICE_EN ??
      "Development notice: do not share personal data. Configure the approved notice before production.",
  };
  return (
    <ChatWidget
      initialLocale={locale}
      apiUrl={apiUrl}
      parentOrigin={parentOrigin}
      parentPage={first(params.parentPage)}
      referrer={first(params.referrer)}
      noticeVersion={noticeVersion}
      privacyNotice={privacyNotice}
      utm={{
        source: first(params.utm_source),
        medium: first(params.utm_medium),
        campaign: first(params.utm_campaign),
      }}
    />
  );
}
