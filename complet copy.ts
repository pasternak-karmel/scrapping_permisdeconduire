import { writeFile, unlink } from "fs/promises";
import twilio from "twilio";

const ALL_PERMIS = ["A", "B"];
const ALL_DEPARTEMENTS = Array.from({ length: 95 }, (_, i) =>
  String(i + 1).padStart(3, "0")
);

ALL_DEPARTEMENTS.push("971", "972", "973", "974", "976");

const CONFIG = {
  username: Bun.env.PDC_USERNAME!,
  password: Bun.env.PDC_PASSWORD!,
  intervalMinutes: 60,
  maxRetries: 3,
  cookiesFilePath: "./cookies_session.json",

  filters: {
    permisTypes:
      Bun.env.PDC_PERMIS_TYPES === "*"
        ? ALL_PERMIS
        : (Bun.env.PDC_PERMIS_TYPES || "A,B").split(",").filter(Boolean),
    departements:
      Bun.env.PDC_DEPARTEMENTS === "*"
        ? ALL_DEPARTEMENTS
        : (Bun.env.PDC_DEPARTEMENTS || "075").split(",").filter(Boolean),
    scanParCentre: Bun.env.PDC_SCAN_PAR_CENTRE === "true",
  },

  notifications: {
    telegram: {
      enabled: !!Bun.env.TELEGRAM_BOT_TOKEN,
      botToken: Bun.env.TELEGRAM_BOT_TOKEN,
      chatId: Bun.env.TELEGRAM_CHAT_ID,
    },
    discord: {
      enabled: !!Bun.env.DISCORD_WEBHOOK_URL,
      webhookUrl: Bun.env.DISCORD_WEBHOOK_URL,
    },
    twilio: {
      enabled:
        !!Bun.env.TWILIO_ACCOUNT_SID &&
        !!Bun.env.TWILIO_AUTH_TOKEN &&
        !!Bun.env.TWILIO_PHONE_FROM,
      accountSid: Bun.env.TWILIO_ACCOUNT_SID,
      authToken: Bun.env.TWILIO_AUTH_TOKEN,
      phoneFrom: Bun.env.TWILIO_PHONE_FROM,
      phonesTo: Bun.env.TWILIO_PHONES_TO?.split(",").filter(Boolean) || [],
    },
  },
};

interface SessionCookies {
  __cf_bm: string;
  cf_clearance: string;
  etuix: string;
  mod_auth_openidc_session: string;
  eulerian?: number;
  TCPID?: number;
  timestamp: number;
}

interface Centre {
  id: string;
  nom: string;
  codeDepartement: string;
  adresse: string;
  codePostal: string;
  ville: string;
  estFerme: boolean;
}

interface PlaceDisponible {
  date: string;
  horaire: string;
  departement: string;
  centre: string;
  centreId: string;
  ville?: string;
  permisType: string;
  typeEpreuve: string;
  numeroInspecteur: string;
  disponible: boolean;
  statutReservation: string;
}

let currentCookies: SessionCookies | null = null;

async function sendTwilioSMS(
  phoneNumber: string,
  message: string
): Promise<boolean> {
  if (!CONFIG.notifications.twilio.enabled) return false;

  try {
    const client = twilio(
      CONFIG.notifications.twilio.accountSid,
      CONFIG.notifications.twilio.authToken
    );

    const messages = await client.messages.create({
      body: message,
      from: CONFIG.notifications.twilio.phoneFrom,
      to: phoneNumber,
    });

    if (messages.status === "failed") return false;
    console.log(`✅ SMS envoyé à ${phoneNumber}`);
    return true;
  } catch (error: any) {
    console.error(`❌ Erreur envoi SMS à ${phoneNumber}:`, error.message);
    return false;
  }
}

async function sendTwilioNotifications(
  placesByPermis: Record<string, PlaceDisponible[]>
): Promise<void> {
  if (!CONFIG.notifications.twilio.enabled) {
    console.log("ℹ️  Notifications SMS désactivées");
    return;
  }

  if (CONFIG.notifications.twilio.phonesTo.length === 0) {
    console.log("⚠️  Aucun numéro de téléphone configuré");
    return;
  }

  console.log(
    `\n📱 Envoi des SMS à ${CONFIG.notifications.twilio.phonesTo.length} numéro(s)...`
  );

  // Envoyer un SMS par type de permis
  for (const [permisType, places] of Object.entries(placesByPermis)) {
    if (places.length === 0) continue;

    // Grouper par date
    const parDate = places.reduce((acc, p) => {
      if (!acc[p.date]) acc[p.date] = [];
      acc[p.date].push(p);
      return acc;
    }, {} as Record<string, PlaceDisponible[]>);

    const datesSorted = Object.keys(parDate).sort();

    // Construire le message SMS (limité à 1600 caractères)
    let message = `🎉 ${places.length} place(s) PERMIS ${permisType}\n\n`;

    const maxDates = 3; // Limiter pour ne pas dépasser la taille du SMS
    datesSorted.slice(0, maxDates).forEach((date) => {
      const placesDate = parDate[date];
      const dateFr = formatDateFr(date);

      message += `📅 ${dateFr}\n`;

      // Grouper par centre
      const parCentre = placesDate.reduce((acc, p) => {
        const key = p.centre;
        if (!acc[key]) acc[key] = [];
        acc[key].push(p);
        return acc;
      }, {} as Record<string, PlaceDisponible[]>);

      const centresLimited = Object.entries(parCentre).slice(0, 3);
      centresLimited.forEach(([centre, slots]) => {
        const horaires = slots
          .slice(0, 2)
          .map((s) => s.horaire)
          .join(", ");
        const ville = slots[0].ville ? ` (${slots[0].ville})` : "";
        message += `🏢 ${centre.substring(0, 30)}${ville}\n⏰ ${horaires}\n`;
      });

      message += "\n";
    });

    if (datesSorted.length > maxDates) {
      message += `... et ${datesSorted.length - maxDates} autre(s) date(s)\n\n`;
    }

    message += `🔗 pro.permisdeconduire.gouv.fr`;

    // Limiter la taille du message
    if (message.length > 1600) {
      message = message.substring(0, 1597) + "...";
    }

    // Envoyer à tous les numéros
    for (const phoneNumber of CONFIG.notifications.twilio.phonesTo) {
      await sendTwilioSMS(phoneNumber, message);
      // Délai entre les envois pour respecter les limites de l'API
      await new Promise((r) => setTimeout(r, 1000));
    }
  }
}

async function sendTelegramNotification(message: string): Promise<boolean> {
  if (!CONFIG.notifications.telegram.enabled) return false;

  try {
    const response = await fetch(
      `https://api.telegram.org/bot${CONFIG.notifications.telegram.botToken}/sendMessage`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          chat_id: CONFIG.notifications.telegram.chatId,
          text: message,
          parse_mode: "HTML",
        }),
      }
    );

    if (!response.ok) {
      console.error("❌ Erreur Telegram:", await response.text());
      return false;
    }

    console.log("✅ Notification Telegram envoyée");
    return true;
  } catch (error: any) {
    console.error("❌ Erreur envoi Telegram:", error.message);
    return false;
  }
}

async function sendDiscordNotification(
  message: string,
  places?: PlaceDisponible[]
): Promise<boolean> {
  if (!CONFIG.notifications.discord.enabled) return false;

  try {
    const embed = {
      title: "🎉 Places disponibles trouvées !",
      description: message,
      color: 0x00ff00,
      timestamp: new Date().toISOString(),
      fields:
        places?.slice(0, 10).map((place) => ({
          name: `${place.permisType} - ${place.typeEpreuve} - ${place.date}`,
          value: `⏰ ${place.horaire}\n🏢 ${place.centre}\n📍 ${
            place.ville || place.departement
          }`,
          inline: false,
        })) || [],
      footer: {
        text: `Total: ${places?.length || 0} place(s)`,
      },
    };

    const response = await fetch(CONFIG.notifications.discord.webhookUrl!, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ embeds: [embed] }),
    });

    if (!response.ok) {
      console.error("❌ Erreur Discord:", await response.text());
      return false;
    }

    console.log("✅ Notification Discord envoyée");
    return true;
  } catch (error: any) {
    console.error("❌ Erreur envoi Discord:", error.message);
    return false;
  }
}

function formatDateFr(dateStr: string): string {
  const date = new Date(dateStr);
  const jours = [
    "dimanche",
    "lundi",
    "mardi",
    "mercredi",
    "jeudi",
    "vendredi",
    "samedi",
  ];
  const mois = [
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
  ];

  const jourSemaine = jours[date.getDay()];
  const jour = date.getDate();
  const moisNom = mois[date.getMonth()];
  const annee = date.getFullYear();

  return `${jourSemaine} ${jour} ${moisNom} ${annee}`;
}

async function notifyPlacesDisponibles(places: PlaceDisponible[]) {
  const count = places.length;

  // Grouper par type de permis pour les SMS
  const placesByPermis = places.reduce((acc, p) => {
    if (!acc[p.permisType]) acc[p.permisType] = [];
    acc[p.permisType].push(p);
    return acc;
  }, {} as Record<string, PlaceDisponible[]>);

  // Grouper par date pour Telegram/Discord
  const parDate = places.reduce((acc, p) => {
    if (!acc[p.date]) acc[p.date] = [];
    acc[p.date].push(p);
    return acc;
  }, {} as Record<string, PlaceDisponible[]>);

  // Trier les dates
  const datesSorted = Object.keys(parDate).sort();

  // Construire le message détaillé pour Telegram
  let details = "";
  const maxDatesToShow = 5;

  datesSorted.slice(0, maxDatesToShow).forEach((date) => {
    const placesDate = parDate[date];
    const dateFr = formatDateFr(date);

    details += `\n📅 <b>${dateFr}</b>\n`;

    // Grouper par centre pour cette date
    const parCentre = placesDate.reduce((acc, p) => {
      const key = `${p.permisType} - ${p.centre}`;
      if (!acc[key]) acc[key] = [];
      acc[key].push(p);
      return acc;
    }, {} as Record<string, PlaceDisponible[]>);

    Object.entries(parCentre).forEach(([centre, slots]) => {
      const horaires = slots.map((s) => s.horaire).join(", ");
      const ville = slots[0].ville ? ` (${slots[0].ville})` : "";
      details += `  🏢 ${centre}${ville}\n`;
      details += `     ⏰ ${horaires}\n`;
    });
  });

  if (datesSorted.length > maxDatesToShow) {
    details += `\n... et ${
      datesSorted.length - maxDatesToShow
    } autre(s) date(s)`;
  }

  const message = `
🎉 <b>${count} NOUVELLE(S) PLACE(S) DÉTECTÉE(S) !</b>
${details}

🔗 <a href="https://pro.permisdeconduire.gouv.fr/reserver-examen">Réserver maintenant</a>
  `.trim();

  await Promise.all([
    sendTelegramNotification(message),
    sendDiscordNotification(`${count} place(s) disponible(s)`, places),
    sendTwilioNotifications(placesByPermis),
  ]);
}

async function login(
  forceNew: boolean = false
): Promise<SessionCookies | null> {
  console.log("\n🔐 Connexion automatique...");

  try {
    // Essayer de charger les cookies existants (sauf si forceNew)
    if (!forceNew) {
      try {
        const file = Bun.file(CONFIG.cookiesFilePath);
        if (await file.exists()) {
          const data = await file.json();

          const age = Date.now() - data.timestamp;
          const twoHours = 2 * 60 * 60 * 1000;

          if (age < twoHours) {
            console.log("✅ Cookies chargés depuis le fichier");
            console.log(`   ℹ️  Âge: ${Math.round(age / 1000 / 60)} minutes`);
            return data;
          } else {
            console.log(
              "⚠️  Cookies expirés (> 2h), nouvelle connexion nécessaire"
            );
          }
        }
      } catch (error) {
        console.log("ℹ️  Aucun cookie sauvegardé trouvé");
      }
    } else {
      console.log("🔄 Forçage d'une nouvelle connexion...");
      try {
        await unlink(CONFIG.cookiesFilePath);
      } catch {}
    }

    // Nouvelle connexion via Puppeteer
    console.log("🌐 Ouverture du navigateur pour authentification...");
    const { getSessionCookiesPDC } = await import("./puppeteerLogin");
    const cookies = await getSessionCookiesPDC(
      CONFIG.username,
      CONFIG.password
    );

    if (!cookies || cookies.length === 0) {
      console.error("❌ Échec de récupération des cookies");
      return null;
    }

    const sessionCookies: Partial<SessionCookies> = {};
    cookies.forEach((cookie: any) => {
      if (cookie.name && cookie.value) {
        sessionCookies[cookie.name as keyof SessionCookies] = cookie.value;
      }
    });

    sessionCookies.timestamp = Date.now();

    // Vérifier que tous les cookies essentiels sont présents
    const requiredCookies = [
      "cf_clearance",
      "mod_auth_openidc_session",
      "__cf_bm",
    ];
    const missingCookies = requiredCookies.filter(
      (c) => !sessionCookies[c as keyof SessionCookies]
    );

    if (missingCookies.length > 0) {
      console.error(`❌ Cookies manquants: ${missingCookies.join(", ")}`);
      return null;
    }

    await writeFile(
      CONFIG.cookiesFilePath,
      JSON.stringify(sessionCookies, null, 2)
    );
    console.log("✅ Nouveaux cookies sauvegardés");

    return sessionCookies as SessionCookies;
  } catch (error: any) {
    console.error("❌ Erreur lors du login:", error.message);
    return null;
  }
}

function buildCookieHeader(cookies: SessionCookies): string {
  const parts = [
    `cf_clearance=${cookies.cf_clearance}`,
    `mod_auth_openidc_session=${cookies.mod_auth_openidc_session}`,
    `__cf_bm=${cookies.__cf_bm}`,
  ];

  if (cookies.etuix) parts.push(`etuix=${cookies.etuix}`);

  return parts.join("; ");
}

async function callPDCApi(
  cookies: SessionCookies,
  endpoint: string,
  options: RequestInit = {}
): Promise<any> {
  const url = `https://pro.permisdeconduire.gouv.fr${endpoint}`;

  const headers: HeadersInit = {
    accept: "application/json, text/plain, */*",
    "accept-language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
    cookie: buildCookieHeader(cookies),
    origin: "https://pro.permisdeconduire.gouv.fr",
    priority: "u=1, i",
    referer: "https://pro.permisdeconduire.gouv.fr/reserver-examen",
    "sec-ch-ua":
      '"Chromium";v="142", "Google Chrome";v="142", "Not_A Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "user-agent":
      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
    ...options.headers,
  };

  try {
    const response = await fetch(url, {
      ...options,
      headers,
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error(`❌ HTTP ${response.status} sur ${endpoint}`);
      console.error(`   Body:`, errorText.substring(0, 200));

      // Si 400/401/403, les cookies sont probablement invalides
      if ([400, 401, 403].includes(response.status)) {
        console.error(
          `   ⚠️  Les cookies semblent invalides (code ${response.status})`
        );
      }

      return null;
    }

    const contentType = response.headers.get("content-type");
    if (contentType?.includes("application/json")) {
      return await response.json();
    } else {
      return await response.text();
    }
  } catch (error: any) {
    console.error(`❌ Erreur fetch sur ${endpoint}:`, error.message);
    return null;
  }
}

// Récupérer la liste des centres d'un département
async function getCentres(
  cookies: SessionCookies,
  permisType: string,
  departement: string
): Promise<Centre[]> {
  const endpoint = "/api/v2/auto-ecole/centres/recherche";

  const result = await callPDCApi(cookies, endpoint, {
    method: "POST",
    headers: {
      "content-type": "application/json",
    },
    body: JSON.stringify({
      filtre: {
        codeDepartement: departement,
        groupePermis: permisType,
      },
    }),
  });

  if (!result || !Array.isArray(result)) return [];

  // Filtrer les centres fermés
  return result.filter((c: Centre) => !c.estFerme);
}

// Rechercher planning par département
async function rechercherPlanningDepartement(
  cookies: SessionCookies,
  permisType: string,
  departement: string
): Promise<any> {
  const endpoint = "/api/v2/auto-ecole/planning/recherche";

  // L'API nécessite une date de début
  const today = new Date().toISOString().split("T")[0];

  return await callPDCApi(cookies, endpoint, {
    method: "POST",
    headers: {
      "content-type": "application/json",
    },
    body: JSON.stringify({
      filtre: {
        date: today,
        codeDepartement: departement,
        groupePermis: permisType,
      },
    }),
  });
}

// Rechercher planning par centre (plus précis)
async function rechercherPlanningCentre(
  cookies: SessionCookies,
  permisType: string,
  centreId: string,
  date: string
): Promise<any> {
  const endpoint = "/api/v2/auto-ecole/planning/recherche";

  return await callPDCApi(cookies, endpoint, {
    method: "POST",
    headers: {
      "content-type": "application/json",
    },
    body: JSON.stringify({
      filtre: {
        date: date,
        groupePermis: permisType,
        centreId: centreId,
      },
    }),
  });
}

function parseAPIResponse(
  result: any,
  permis: string,
  dept: string,
  centresMap?: Map<string, Centre>
): PlaceDisponible[] {
  const places: PlaceDisponible[] = [];

  if (!result || !Array.isArray(result)) return places;

  try {
    result.forEach((item: any) => {
      const creneau = item.creneauDuPlanning;
      if (!creneau) return;

      // Filtrer uniquement les créneaux DISPONIBLES
      const isDisponible =
        !creneau.statutDeReservation ||
        creneau.statutDeReservation === "DISPONIBLE" ||
        creneau.statutDeReservation === "NON_RÉSERVÉ";

      if (!isDisponible) return; // Skip les places occupées

      // Parser la date/heure
      const dateDebut = new Date(creneau.dateHeureDebut);
      const dateFin = new Date(creneau.dateHeureFin);

      const date = dateDebut.toISOString().split("T")[0];
      const heureDebut = dateDebut.toLocaleTimeString("fr-FR", {
        hour: "2-digit",
        minute: "2-digit",
      });
      const heureFin = dateFin.toLocaleTimeString("fr-FR", {
        hour: "2-digit",
        minute: "2-digit",
      });
      const horaire = `${heureDebut}-${heureFin}`;

      // Récupérer les infos du centre depuis la map si disponible
      const centreInfo = centresMap?.get(creneau.centre?.id);

      places.push({
        date,
        horaire,
        departement: dept,
        centre: creneau.centre?.nom || "Centre inconnu",
        centreId: creneau.centre?.id || "",
        ville: centreInfo?.ville,
        permisType: creneau.groupePermis || permis,
        typeEpreuve: creneau.typeEpreuvePratique || "CIRCULATION",
        numeroInspecteur: creneau.numeroInspecteur || "",
        disponible: true,
        statutReservation: creneau.statutDeReservation || "DISPONIBLE",
      });
    });
  } catch (error: any) {
    console.error(`⚠️  Erreur parsing:`, error.message);
  }

  return places;
}

async function scanAllFilters(
  cookies: SessionCookies
): Promise<PlaceDisponible[] | null> {
  const permisToScan = CONFIG.filters.permisTypes;
  const deptsToScan = CONFIG.filters.departements;

  console.log(`\n📊 Scan prévu:`);
  console.log(`   • Permis: ${permisToScan.join(", ")}`);
  console.log(`   • Départements: ${deptsToScan.join(", ")}`);
  console.log(
    `   • Mode: ${
      CONFIG.filters.scanParCentre
        ? "Par centre (précis)"
        : "Par département (rapide)"
    }`
  );

  const allPlaces: PlaceDisponible[] = [];
  let hasAuthError = false;

  for (const permis of permisToScan) {
    for (const dept of deptsToScan) {
      console.log(`\n🔍 ${permis} - Dept ${dept}`);

      // Récupérer la liste des centres (requis pour les deux modes)
      const centres = await getCentres(cookies, permis, dept);

      if (centres === null) {
        hasAuthError = true;
        break;
      }

      if (centres.length === 0) {
        console.log(`   ⚠️  Aucun centre trouvé`);
        continue;
      }

      console.log(`   📍 ${centres.length} centre(s) trouvé(s)`);

      // Créer une map des centres pour enrichir les résultats
      const centresMap = new Map(centres.map((c) => [c.id, c]));

      if (CONFIG.filters.scanParCentre) {
        // Mode 1: Scanner chaque centre individuellement (plus précis)
        const today = new Date().toISOString().split("T")[0];

        for (const centre of centres) {
          process.stdout.write(`\r   🏢 ${centre.nom.substring(0, 30)}...`);

          const planning = await rechercherPlanningCentre(
            cookies,
            permis,
            centre.id,
            today
          );

          if (planning === null) {
            hasAuthError = true;
            break;
          }

          if (planning && planning.length > 0) {
            const places = parseAPIResponse(planning, permis, dept, centresMap);
            if (places.length > 0) {
              console.log(`\n      ✅ ${places.length} place(s) !`);
              allPlaces.push(...places);
            }
          }

          await new Promise((r) => setTimeout(r, 300));
        }

        if (hasAuthError) break;
      } else {
        // Mode 2: Scanner avec le premier centre du département (plus rapide)
        const premierCentre = centres[0];
        const today = new Date().toISOString().split("T")[0];

        console.log(`   🏢 Scan via: ${premierCentre.nom}`);

        const planning = await rechercherPlanningCentre(
          cookies,
          permis,
          premierCentre.id,
          today
        );

        if (planning === null) {
          hasAuthError = true;
          break;
        }

        if (planning && planning.length > 0) {
          const places = parseAPIResponse(planning, permis, dept, centresMap);
          if (places.length > 0) {
            console.log(`   ✅ ${places.length} place(s) disponible(s) !`);
            allPlaces.push(...places);
          } else {
            console.log(`   ❌ Aucune place disponible`);
          }
        } else {
          console.log(`   ❌ Aucune place disponible`);
        }
      }

      if (hasAuthError) break;

      await new Promise((r) => setTimeout(r, 500));
    }

    if (hasAuthError) break;
  }

  console.log("\n");

  // Retourner null si erreur d'authentification
  return hasAuthError ? null : allPlaces;
}

let isShuttingDown = false;

process.on("SIGINT", async () => {
  if (isShuttingDown) return;
  isShuttingDown = true;

  console.log("\n\n🛑 Arrêt demandé...");

  if (currentCookies) {
    try {
      await writeFile(
        CONFIG.cookiesFilePath,
        JSON.stringify(currentCookies, null, 2)
      );
      console.log("💾 Cookies sauvegardés avant arrêt");
    } catch (e) {
      console.error("❌ Erreur sauvegarde cookies:", e);
    }
  }

  console.log("👋 Arrêt propre effectué");
  process.exit(0);
});

async function surveillerPlaces() {
  console.log(`🔄 Démarrage de la surveillance automatique\n`);
  console.log(`⏰ Intervalle: ${CONFIG.intervalMinutes} minutes\n`);

  currentCookies = await login();
  if (!currentCookies) {
    console.error("❌ Impossible de se connecter");
    return;
  }

  let consecutiveErrors = 0;

  while (!isShuttingDown) {
    const now = new Date().toLocaleString("fr-FR");
    console.log(`\n${"=".repeat(70)}`);
    console.log(`⏰ Scan complet à ${now}`);
    console.log("=".repeat(70));

    try {
      const places = await scanAllFilters(currentCookies!);

      // Si null, c'est une erreur d'authentification
      if (places === null) {
        console.log("\n🔄 Tentative de reconnexion...");
        currentCookies = await login(true);

        if (!currentCookies) {
          console.error("❌ Échec de reconnexion");
          consecutiveErrors++;

          if (consecutiveErrors >= CONFIG.maxRetries) {
            console.error(
              "❌ Trop d'erreurs consécutives - arrêt de la surveillance"
            );
            break;
          }

          console.log("⏳ Attente avant nouvelle tentative...");
          await new Promise((resolve) => setTimeout(resolve, 5 * 60 * 1000)); // 5 min
          continue;
        }

        console.log("✅ Reconnexion réussie, reprise du scan...");
        continue; // Recommencer immédiatement
      }

      if (places.length > 0) {
        console.log(
          `\n🎉🎉🎉 ${places.length} PLACE(S) DISPONIBLE(S) ! 🎉🎉🎉`
        );

        const groupes = places.reduce((acc, p) => {
          const key = `${p.permisType} - ${p.centre}`;
          if (!acc[key]) acc[key] = [];
          acc[key].push(p);
          return acc;
        }, {} as Record<string, PlaceDisponible[]>);

        console.log("\n📋 Détails:");
        Object.entries(groupes).forEach(([key, slots]) => {
          console.log(`\n  ${key}: ${slots.length} place(s)`);
          slots.slice(0, 3).forEach((s) => {
            console.log(`    • ${s.date} ${s.horaire} (${s.typeEpreuve})`);
          });
          if (slots.length > 3) {
            console.log(`    ... et ${slots.length - 3} autre(s)`);
          }
        });

        await writeFile(
          "places_disponibles.json",
          JSON.stringify(places, null, 2)
        );
        console.log("\n💾 Résultats sauvegardés");

        await notifyPlacesDisponibles(places);
      } else {
        console.log("\n❌ Aucune place disponible pour le moment");
      }

      consecutiveErrors = 0;
    } catch (error: any) {
      consecutiveErrors++;
      console.error(
        `❌ Erreur (${consecutiveErrors}/${CONFIG.maxRetries}):`,
        error.message
      );

      if (consecutiveErrors >= CONFIG.maxRetries) {
        console.error(
          "❌ Trop d'erreurs consécutives - arrêt de la surveillance"
        );
        break;
      }
    }

    if (!isShuttingDown) {
      console.log(
        `\n⏳ Prochain scan dans ${CONFIG.intervalMinutes} minutes...`
      );
      await new Promise((resolve) =>
        setTimeout(resolve, CONFIG.intervalMinutes * 60 * 1000)
      );
    }
  }
}

const args = Bun.argv.slice(2);

if (args.includes("--watch") || args.includes("-w")) {
  await surveillerPlaces();
} else {
  currentCookies = await login();
  if (!currentCookies) {
    console.log("❌ Impossible de récupérer les cookies automatiquement");
    process.exit(1);
  }

  const places = await scanAllFilters(currentCookies);

  if (places === null) {
    console.log("\n⚠️  Erreur d'authentification détectée");
    console.log("🔄 Tentative avec de nouveaux cookies...");

    currentCookies = await login(true);
    if (!currentCookies) {
      console.log("❌ Échec de la reconnexion");
      process.exit(1);
    }

    const retryPlaces = await scanAllFilters(currentCookies);
    if (retryPlaces === null) {
      console.log("❌ Toujours en échec après reconnexion");
      process.exit(1);
    }

    // Continuer avec retryPlaces...
    console.log(`\n📊 Résultat: ${retryPlaces.length} place(s) disponible(s)`);

    if (retryPlaces.length > 0) {
      const byPermis = retryPlaces.reduce((acc, p) => {
        acc[p.permisType] = (acc[p.permisType] || 0) + 1;
        return acc;
      }, {} as Record<string, number>);

      console.log("\n📈 Par type de permis:");
      Object.entries(byPermis).forEach(([permis, count]) => {
        console.log(`   • ${permis}: ${count} place(s)`);
      });

      await notifyPlacesDisponibles(retryPlaces);

      await writeFile(
        "places_disponibles.json",
        JSON.stringify(retryPlaces, null, 2)
      );
      console.log("\n💾 Résultats sauvegardés dans places_disponibles.json");
    }
  } else {
    console.log(`\n📊 Résultat: ${places.length} place(s) disponible(s)`);

    if (places.length > 0) {
      const byPermis = places.reduce((acc, p) => {
        acc[p.permisType] = (acc[p.permisType] || 0) + 1;
        return acc;
      }, {} as Record<string, number>);

      console.log("\n📈 Par type de permis:");
      Object.entries(byPermis).forEach(([permis, count]) => {
        console.log(`   • ${permis}: ${count} place(s)`);
      });

      await notifyPlacesDisponibles(places);

      await writeFile(
        "places_disponibles.json",
        JSON.stringify(places, null, 2)
      );
      console.log("\n💾 Résultats sauvegardés dans places_disponibles.json");
    }
  }
}
