import { ScrapeConfig, ScrapflyClient } from "@scrapfly/scrapfly-sdk";

const client = new ScrapflyClient({
  key: Bun.env.SCRAPFLY_API_KEY!,
});


async function scrapePlacesExamen() {
  try {
    console.log(
      "🔍 Scraping des places disponibles avec proxy résidentiel...\n"
    );

    let cookies;
      const file = Bun.file("./cookies_session.json");
      if (await file.exists()) {
        cookies = await file.json();
      }
    
    const response = await client.scrape(
      new ScrapeConfig({
        url: "https://pro.permisdeconduire.gouv.fr/reserver-examen",
        cookies: cookies,
        country: "fr",
        proxy_pool: "public_residential_pool",
        cost_budget: 10,
        asp: true,
        render_js: true,
        rendering_wait: 8000,
        wait_for_selector: ".ds-PlanningCell",
        session: `session_${Date.now()}`,
        headers: {
          "User-Agent":
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
          Accept:
            "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
          "Accept-Language": "fr-FR,fr;q=0.9",
          Referer: "https://pro.permisdeconduire.gouv.fr/",
        },
        js: `
  await new Promise(resolve => setTimeout(resolve, 5000));
  
  const extractPlaces = () => {
    const places = [];
    
    const planningCells = document.querySelectorAll('.ds-PlanningCell');
    
    planningCells.forEach((cell, index) => {
      // Extraire directement depuis le HTML brut
      const cellHTML = cell.innerHTML;
      
      // Extraire l'horaire avec regex
      const horaireMatch = cellHTML.match(/plage-horaire[^>]*>([^<]+)</);
      const plageHoraire = horaireMatch ? horaireMatch[1].trim() : null;
      
      // Extraire le statut avec regex
      const statusMatch = cellHTML.match(/>(Place\s+occupée|Place\s+disponible|Disponible|Indisponible)</i);
      const statusText = statusMatch ? statusMatch[1].trim() : '';
      
      // Alternative: chercher dans tout le HTML
      const isOccupee = cellHTML.toLowerCase().includes('occupée') || 
                        cellHTML.toLowerCase().includes('occupé');
      const isIndisponible = cellHTML.toLowerCase().includes('indisponible');
      
      const isAvailable = !isOccupee && !isIndisponible;
      
      places.push({
        index: index,
        horaire: plageHoraire,
        statut: statusText,
        disponible: isAvailable,
        texteComplet: cell.innerText?.trim() || '',
        classes: cell.className,
        html: cellHTML.substring(0, 300),
        htmlLength: cellHTML.length,
      });
    });
    
    return places;
  };
  
  const allPlaces = extractPlaces();
  
  const placesDisponibles = allPlaces.filter(p => p.disponible);
  const placesOccupees = allPlaces.filter(p => !p.disponible);
  
  const dates = Array.from(document.querySelectorAll('[class*="date"], [class*="jour"], [class*="day"]')).map(el => ({
    text: el.innerText?.trim(),
    classes: el.className
  })).slice(0, 10);
  
  return JSON.stringify({
    summary: {
      total: allPlaces.length,
      disponibles: placesDisponibles.length,
      occupees: placesOccupees.length,
    },
    placesDisponibles: placesDisponibles,
    placesOccupees: placesOccupees,
    toutesLesPlaces: allPlaces,
    dates: dates,
    pageInfo: {
      title: document.title,
      url: window.location.href,
      isLoggedIn: !document.body.innerText.includes("Se connecter"),
    }
  });
`,
      })
    );

    console.log("✅ Status:", response.result?.status_code);
    console.log("💰 Durée:", response.result?.duration, "crédits");

    if (response.result?.browser_data?.javascript_evaluation_result) {
      const data = JSON.parse(
        response.result.browser_data.javascript_evaluation_result
      );

      console.log("\n📊 RÉSUMÉ:");
      console.log(`Total de places: ${data.summary.total}`);
      console.log(`✅ Places disponibles: ${data.summary.disponibles}`);
      console.log(`❌ Places occupées: ${data.summary.occupees}`);
      console.log(
        `Connecté: ${data.pageInfo.isLoggedIn ? "✅ OUI" : "❌ NON"}`
      );

      if (data.summary.disponibles > 0) {
        console.log("\n🎯 PLACES DISPONIBLES:");
        data.placesDisponibles.forEach((place) => {
          console.log(
            `  ⏰ ${place.horaire} - ✅ ${place.statut || "DISPONIBLE"}`
          );
        });
      }

      if (data.summary.occupees > 0) {
        console.log("\n❌ PLACES OCCUPÉES (échantillon):");
        data.placesOccupees.slice(0, 5).forEach((place) => {
          console.log(`  ⏰ ${place.horaire} - ❌ ${place.statut}`);
        });
      }

      // Sauvegarder les résultats
      await Bun.write("places_disponibles.json", JSON.stringify(data, null, 2));
      console.log(
        "\n💾 Résultats complets sauvegardés dans: places_disponibles.json"
      );

      // Sauvegarder un CSV simple
      const csvLines = [
        "Horaire,Disponible,Statut",
        ...data.toutesLesPlaces.map(
          (p) =>
            `"${p.horaire}","${p.disponible ? "OUI" : "NON"}","${p.statut}"`
        ),
      ];
      await Bun.write("places_disponibles.csv", csvLines.join("\n"));
      console.log("💾 CSV sauvegardé dans: places_disponibles.csv");

      // Sauvegarder le HTML
      if (response.result?.content) {
        await Bun.write("page_reserver_examen.html", response.result.content);
        console.log(
          "💾 HTML complet sauvegardé dans: page_reserver_examen.html"
        );
      }

      return data;
    }
  } catch (error: any) {
    console.error("❌ Erreur:", error.message);
    console.error(error);
  }
}

// Fonction pour surveiller les places disponibles
async function surveillerPlaces(intervalMinutes = 5) {
  console.log(
    `🔄 Surveillance lancée (vérification toutes les ${intervalMinutes} minutes)\n`
  );

  while (true) {
    const now = new Date().toLocaleString("fr-FR");
    console.log(`\n⏰ Vérification à ${now}`);

    const data = await scrapePlacesExamen();

    if (data && data.summary.disponibles > 0) {
      console.log(
        `\n🎉 ${data.summary.disponibles} place(s) disponible(s) détectée(s) !`
      );
      // Tu peux ajouter une notification ici (email, SMS, webhook, etc.)
    }

    console.log(
      `\n⏳ Prochaine vérification dans ${intervalMinutes} minutes...`
    );
    await new Promise((resolve) =>
      setTimeout(resolve, intervalMinutes * 60 * 1000)
    );
  }
}

// Utilisation simple
await scrapePlacesExamen();

// Ou activer la surveillance continue (décommenter pour utiliser)
// await surveillerPlaces(5); // Vérifie toutes les 5 minutes
