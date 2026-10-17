export type EventBannerPartner = {
  name: string;
  logo: string;
  href?: string;
};

export type EventBannerEvent = {
  id: string;
  eyebrow?: string;
  pulse?: boolean;
  title: string;
  titleMobile?: string;
  subtitle?: string;
  url: string;
  cta: string;
  startsAt: string;
  endsAt: string;
  partner?: EventBannerPartner;
  analyticsId: string;
  storageKey: string;
};

// Audible announcements
export const events: EventBannerEvent[] = [];
