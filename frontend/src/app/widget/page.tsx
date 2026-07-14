import ChatWidget from "@/components/chat-widget";

type WidgetPageProps = {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

function first(value: string | string[] | undefined) {
  return Array.isArray(value) ? value[0] : value;
}

export default async function WidgetPage({ searchParams }: WidgetPageProps) {
  const params = await searchParams;
  const locale = first(params.locale) === "en" ? "en" : "es";
  const apiUrl =
    first(params.apiUrl) ?? process.env.NEXT_PUBLIC_CHAT_API_URL ?? "http://localhost:8000";
  const parentOrigin = first(params.parentOrigin) ?? "http://localhost:3000";
  return (
    <ChatWidget
      initialLocale={locale}
      apiUrl={apiUrl.replace(/\/$/, "")}
      parentOrigin={parentOrigin.replace(/\/$/, "")}
      parentPage={first(params.parentPage)}
      referrer={first(params.referrer)}
      utm={{
        source: first(params.utm_source),
        medium: first(params.utm_medium),
        campaign: first(params.utm_campaign),
        term: first(params.utm_term),
        content: first(params.utm_content),
      }}
    />
  );
}
