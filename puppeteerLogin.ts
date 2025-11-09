import puppeteer from 'puppeteer-extra';
import StealthPlugin from 'puppeteer-extra-plugin-stealth';
import axios from 'axios';

puppeteer.use(StealthPlugin());

const CAPTCHA_API_KEY = Bun.env.CAPTCHA_API_KEY!;
if (!CAPTCHA_API_KEY) throw new Error("❌ CAPTCHA_API_KEY manquant dans Bun.env");

interface TurnstileResponse {
  status: number;
  request: string;
}

async function solveTurnstile2Captcha(sitekey: string, pageUrl: string, maxRetries = 3): Promise<string | null> {
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      console.log(`🔄 Tentative ${attempt}/${maxRetries} de résolution du captcha...`);
      
      const submit = await axios.post<TurnstileResponse>(
        "https://2captcha.com/in.php",
        null,
        {
          params: {
            key: CAPTCHA_API_KEY,
            method: "turnstile",
            sitekey,
            pageurl: pageUrl,
            json: 1,
          },
          timeout: 30000,
        }
      );

      if (submit.data.status !== 1) {
        console.error(`❌ Erreur 2Captcha (tentative ${attempt}):`, submit.data.request);
        if (attempt < maxRetries) {
          await Bun.sleep(5000);
          continue;
        }
        return null;
      }

      const taskId = submit.data.request;
      console.log(`✅ Tâche créée: ${taskId}`);
      console.log("⏳ Attente de la résolution (30-120s)...");

      const maxAttempts = 40;
      for (let i = 0; i < maxAttempts; i++) {
        await Bun.sleep(3000);

        const result = await axios.get<TurnstileResponse>(
          "https://2captcha.com/res.php",
          {
            params: {
              key: CAPTCHA_API_KEY,
              action: "get",
              id: taskId,
              json: 1,
            },
            timeout: 30000,
          }
        );

        if (result.data.status === 1) {
          console.log("✅ Captcha résolu avec succès !");
          return result.data.request;
        }

        if (result.data.request !== "CAPCHA_NOT_READY") {
          console.error(`❌ Erreur inattendue: ${result.data.request}`);
          break;
        }

        if (i % 10 === 0 && i > 0) {
          console.log(`   ⏳ ${i * 3}s écoulées...`);
        }
      }

      console.error(`❌ Timeout: 2Captcha trop lent (>120s) - tentative ${attempt}`);
      if (attempt < maxRetries) {
        await Bun.sleep(5000);
        continue;
      }
      
    } catch (e: any) {
      console.error(`❌ Erreur réseau 2Captcha (tentative ${attempt}):`, e.message);
      if (attempt < maxRetries) {
        await Bun.sleep(5000);
        continue;
      }
    }
  }
  
  return null;
}

export async function getSessionCookiesPDC(username: string, password: string, { debug = false } = {}) {
  // ✅ CORRECTION 1: Validation des credentials
  if (!username || !password) {
    console.error("❌ Username ou password manquant");
    return null;
  }

  const browser = await puppeteer.launch({
    headless: !debug,
    args: [
      "--no-sandbox",
      "--disable-setuid-sandbox",
      "--disable-blink-features=AutomationControlled",
      "--disable-web-security",
      "--window-size=1920,1080",
    ],
  });

  try {
    const page = await browser.newPage();

    await page.setUserAgent(
      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    );

    await page.evaluateOnNewDocument(() => {
      Object.defineProperty(navigator, "webdriver", { get: () => undefined });
      Object.defineProperty(navigator, "plugins", { get: () => [1, 2, 3, 4, 5] });
      (window as any).chrome = { runtime: {} };
    });

    const authUrl = "https://pro.permisdeconduire.gouv.fr/?groupe-permis=B&date=2025-11-05";

    console.log("\n📡 Chargement de la page de login...");
    await page.goto(authUrl, { waitUntil: "networkidle2", timeout: 60000 });

    await page.waitForSelector("#username", { timeout: 20000 });
    
    // Remplissage
    await page.type("#username", username, { delay: 100 });
    await Bun.sleep(400);
    await page.type("#password", password, { delay: 100 });

    await page.waitForFunction(
      () =>
        document.querySelector("iframe[src*='challenges.cloudflare.com']") ||
        document.querySelector("[data-sitekey]"),
      { timeout: 30000 }
    );

    const sitekey = await page.evaluate(() => {
      const iframe = document.querySelector("iframe[src*='challenges.cloudflare.com']");
      if (iframe) {
        const src = iframe.getAttribute("src");
        const match = src?.match(/sitekey=([^&]+)/);
        if (match) return match[1];
      }
      const div = document.querySelector("[data-sitekey]");
      return div?.getAttribute("data-sitekey") ?? null;
    });

    if (!sitekey) {
      console.error("❌ Sitekey Turnstile introuvable");
      return null;
    }

    console.log(`✅ Sitekey: ${sitekey.substring(0, 30)}...`);

    // ✅ CORRECTION 2: Retry sur le captcha
    const turnstileToken = await solveTurnstile2Captcha(sitekey, page.url(), 3);
    if (!turnstileToken) {
      console.error("❌ Impossible de résoudre le Turnstile après 3 tentatives");
      return null;
    }

    console.log("💉 Injection robuste du token Turnstile et préparation du submit...");

    try {
      await page.evaluate((token) => {
        const form = document.querySelector('form') as HTMLFormElement | null;
        if (!form) {
          throw new Error('Formulaire introuvable pour injection du token.');
        }

        const ensureHidden = (name: string, value: string) => {
          let el = form.querySelector(`input[name="${name}"]`) as HTMLInputElement | null;
          if (!el) {
            el = document.createElement('input');
            el.type = 'hidden';
            el.name = name;
            form.appendChild(el);
          }
          el.value = value;
          el.dispatchEvent(new Event('input', { bubbles: true }));
          el.dispatchEvent(new Event('change', { bubbles: true }));
          return el;
        };

        ensureHidden('cf-turnstile-response', token);
        ensureHidden('g-recaptcha-response', token);

        try {
          const w = window as any;
          if (w.turnstile) {
            if (typeof w.turnstile.getResponse === 'function') {
              w.__injected_turnstile_response = token;
            }
            const cbName = form.getAttribute('data-callback') || (form.querySelector('[data-callback]')?.getAttribute('data-callback'));
            if (cbName && typeof (w as any)[cbName] === 'function') {
              try { (w as any)[cbName](token); } catch (e) { /* noop */ }
            }
          }
        } catch (e) {
          // Silencieux
        }
      }, turnstileToken);

      const formPayload: Record<string, string> = await page.evaluate(() => {
        const form = document.querySelector('form') as HTMLFormElement | null;
        const out: Record<string, string> = {};
        if (!form) return out;
        const fd = new FormData(form);
        fd.forEach((v, k) => { out[k] = String(v); });
        return out;
      });

      console.log("➡️ Form payload avant submit:");
      console.log(formPayload);

      let navigationSucceeded = false;
      try {
        console.log("🚀 Soumission via form.submit()...");
        await Promise.all([
          page.waitForNavigation({ waitUntil: 'networkidle2', timeout: 60000 }),
          page.evaluate(() => (document.querySelector('form') as HTMLFormElement).submit()),
        ]);
        navigationSucceeded = true;
      } catch (e: any) {
        console.warn("⚠️ form.submit() échoué, fallback sur click():", e.message);
      }

      if (!navigationSucceeded) {
        try {
          console.log("🔁 Fallback: click() sur #kc-login...");
          await Promise.all([
            page.waitForNavigation({ waitUntil: 'networkidle2', timeout: 60000 }),
            page.click('#kc-login'),
          ]);
          navigationSucceeded = true;
        } catch (e: any) {
          console.warn("⚠️ click() échoué:", e.message);
        }
      }

      await Bun.sleep(1000);

      const finalUrl = page.url();
      console.log(`📍 URL après login: ${finalUrl}`);

      // ✅ CORRECTION 3: Vérification des erreurs Keycloak
      const errorMsg = await page.evaluate(() => {
        const selectors = [
          '.alert-error',
          '#input-error',
          '.kc-feedback-text',
          '[class*="error"]',
          '[class*="invalid"]'
        ];
        
        for (const sel of selectors) {
          const el = document.querySelector(sel);
          if (el && el.textContent?.trim()) {
            return el.textContent.trim();
          }
        }
        return null;
      });

      if (errorMsg) {
        console.error(`❌ Erreur Keycloak détectée: "${errorMsg}"`);
        
        // Sauvegarde pour debug
        try {
          const html = await page.content();
          await Bun.write('puppeteer_keycloak_error.html', html);
          console.log("📄 Page d'erreur sauvegardée → puppeteer_keycloak_error.html");
        } catch (e) {
          console.warn("⚠️ Impossible de sauvegarder le HTML");
        }
        
        return null;
      }

      // Vérification si toujours sur la page d'auth
      if (finalUrl.includes('auth.') || 
          finalUrl.includes('cdn-cgi') || 
          finalUrl.includes('/realms/formation/login-actions')) {
        console.error("❌ Toujours sur la page d'authentification");
        
        try {
          const html = await page.content();
          await Bun.write('puppeteer_error_debug.html', html);
          console.log("📄 Page sauvegardée → puppeteer_error_debug.html");
          
          const cs = await page.cookies();
          await Bun.write('puppeteer_error_cookies.json', JSON.stringify(cs, null, 2));
          console.log("🍪 Cookies sauvegardés → puppeteer_error_cookies.json");
        } catch (e: any) {
          console.warn("⚠️ Impossible de sauvegarder les fichiers debug:", e.message);
        }

        return null;
      }

      console.log("✅ Connexion réussie !");
      const cookies = await page.cookies();

      const important = cookies.filter((c) =>
        ["mod_auth_openidc_session", "__cf_bm", "cf_clearance", "etuix", "eulerian", "TCPID"].includes(c.name)
      );

      const data: Record<string, any> = { timestamp: Date.now() };
      for (const c of important) data[c.name] = c.value;

      await Bun.write("cookies_session.json", JSON.stringify(data, null, 2));
      console.log("💾 Cookies sauvegardés → cookies_session.json");

      return cookies;

    } catch (e: any) {
      console.error("❌ Erreur durant l'injection/soumission:", e.message);
      throw e;
    }

  } catch (error: any) {
    console.error("❌ Erreur fatale Puppeteer:", error.message);
    return null;
  } finally {
    if (debug) {
      console.log("🔍 Mode debug: navigateur laissé ouvert");
      await new Promise(() => {});
    } else {
      await browser.close();
    }
  }
}