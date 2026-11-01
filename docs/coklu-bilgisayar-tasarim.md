# Birden çok bilgisayar tek haritada — tasarım

Durum: öneri (1 Kasım 2026). Kod yazılmadı. Sürüm 0.1.2'ye göre yazıldı.

## 1. Sorun

Qosmopol her bilgisayarda yalnızca **o bilgisayarın diskindeki** Claude Code konularını görür:
`bin/scan.py`, Claude masaüstü uygulamasının yerel `claude-code-sessions` kayıtlarını okur
(macOS'ta `~/Library/Application Support/Claude`, Windows'ta `%APPDATA%\Claude`).
Aynı Claude hesabını iki Mac ve bir Windows'ta kullanan biri her bilgisayarda ayrı bir harita görür;
Mac'te bekleyen bir soru Windows'taki haritada hiç görünmez.

Claude'un sol menüsündeki proje listesi (Projects, beta) hesapla buluttan gelir ve her bilgisayarda
görünür, ama projelerin **konuları** hangi bilgisayarda açıldıysa o bilgisayarın diskinde durur.
Bu yüzden "proje adları her yerde var, konular yok" görüntüsü oluşur.

Hedef: hangi bilgisayarda olursam olayım, **bütün bilgisayarlarımda bekleyen** her şeyi tek haritada
görmek; mümkünse oradan cevap vermek.

## 2. Bugünkü yapının sınırları (ölçüldü)

- Sunucu yalnızca `127.0.0.1`'e bağlanır (`bin/server.py`, `ThreadingHTTPServer(("127.0.0.1", PORT)…)`)
  ve her API çağrısında hem `Host` başlığının `127.0.0.1`/`localhost` olmasını hem de
  `X-Qosmopol-Token` anahtarını ister. Bu, başka sitelerin ve ağdaki başka cihazların sunucuya
  erişememesini sağlar; çok bilgisayarlı tasarım bu güvenliği **gevşetmemeli**.
- Yazma işleri (mesaj gönderme, arşivleme, yeniden açma, model/efor değiştirme) sunucuda kuyruğa
  girer ve **o bilgisayarın** ana oturumundaki eklenti köprüsü (`hooks/register.tsx`, `bridge()`)
  tarafından Claude uygulamasının oturum araçlarıyla yapılır. Başka bilgisayarın Claude uygulamasına
  buradan ulaşmanın yolu yoktur.
- "Uygulamada aç" `claude://claude.ai/epitaxy/<local_id>` bağlantısını kullanır; bu yalnızca konunun
  bulunduğu bilgisayarda çalışır.
- Oturum kayıtlarında `bridgeSessionIds` alanı var (bir Mac'te ölçüldü: 597 oturum kaydının 185'inde,
  arşivlenmemiş 361 kaydın 133'ünde dolu; `session_…` ya da `cse_…` biçiminde). Bunlar Remote Control
  kimlikleri. **1 Kasım'da denendi:** `https://claude.ai/code/<kimlik>` bağlantısı, Remote Control'ü açık
  ya da yakın tarihli konularda claude.ai'nin web sürümünde konuyu bütün konuşmasıyla ve yazma kutusuyla
  açtı (iki konu: biri o an açık, biri bir gün önceki). Temmuz'dan kalma bir konuda "This session couldn't
  be found" döndü. Yani bağlantı her konu için değil, yalnızca Remote Control'ü hâlâ geçerli konular için
  çalışıyor; listenin **son** kimliği kullanılmalı.
- claude.ai/code'un sol menüsü başka bilgisayarlarda açılmış Remote Control konularını da listeliyor
  (Mac'teki tarayıcıda Windows'ta açılan iki konu göründü). Bu listenin belgelenmiş bir arayüzü yok;
  Qosmopol onu kullanıcının claude.ai oturum çerezleriyle okuyamaz ve okumamalı. Ama kullanıcı için
  bugün de çalışan bir yol: başka bilgisayardaki bir konuya claude.ai/code'dan cevap verilebiliyor.
- Kullanıcı gözlemi (1 Kasım): Claude uygulaması bir projeyi (ör. sabitlenmiş bir proje) Mac'te ve
  Windows'ta **birebir ve anlık** aynı gösteriyor; yani Claude konuları kendi bulutu üzerinden canlı
  eşitliyor. Ama uygulamanın eklentilere ve oturumlara verdiği resmî araç (`ccd_session_mgmt`
  `list_sessions`) her iki bilgisayarda da **yalnızca o bilgisayarın** konularını döndürdü (Mac'te 40
  sonucun hepsi Mac klasörlerinde; o gün Windows'ta açılan, daha yeni konular listede yok; Windows'ta
  yalnızca 7 yerel konu). Bu eşitlenmiş veri eklentilere açık değil. Anthropic bunu ileride açarsa
  (ör. `list_sessions`'a başka cihazların konuları) bu tasarımın büyük kısmı gereksizleşir; o zamana
  kadar Qosmopol kendi eşitlemesini yapmak zorunda.
- Claude'un Projects listesi bilgisayarda okunabilir düz bir dosya olarak bulunmadı; uygulamanın kendi
  iç deposunda (tarayıcı depolaması) duruyor. Bunun belgelenmiş bir arayüzü yok.

## 3. Seçenekler

### A. Ortak klasör üzerinden eşitleme (önerilen ilk adım)

Her bilgisayardaki Qosmopol sunucusu, kendi taramasının özetini kullanıcının zaten kullandığı bir
eşitlenen klasöre yazar (iCloud Drive, Google Drive, Dropbox, OneDrive); diğer bilgisayarların
dosyalarını da oradan okur.

```
<eşitlenen klasör>/Qosmopol/
  cihazlar/<cihaz-id>.json     her bilgisayar yalnız kendi dosyasını yazar (çakışma yok)
  gelen/<cihaz-id>/*.json      (2. aşama) o bilgisayara bırakılan işler
```

- `cihaz-id`: ilk açılışta üretilen rastgele kimlik + görünen ad (bilgisayar adı), `~/.qosmopol/cihaz.json`.
- Özet dosyası: `scan.py` çıktısındaki konu satırları (`id, title, proj, last, cat, need, detail,
  busy, ask, acc`; eklenecek `bridge` alanıyla Remote Control kimliği), zaman damgası ve Qosmopol sürümü. `cwd` gibi yerel yollar
  isteğe bağlı olarak çıkarılabilir.
- Her 30 saniyede bir, yalnızca içerik değiştiyse yazılır (eşitleme trafiği az kalsın).
- Okurken: 3 dakikadan eski dosyanın bilgisayarı "çevrimdışı" gösterilir, konuları soluk çizilir.
- Klasör yolu: web görünümündeki ayardan seçilir ve `~/.qosmopol/ayar.json`'a yazılır;
  `QOSMOPOL_SYNC_DIR` ortam değişkeni de kabul edilir. Seçilmezse hiçbir şey değişmez.

Artıları: ağda port açılmaz, sunucu `127.0.0.1`'de kalır; farklı şehirlerdeki bilgisayarlar da
görünür; şifreleme ve erişim eşitleme servisinin kendisinde; ek sunucu ve aylık maliyet yok;
Python'un standart kütüphanesi yeter (paket şartı eklenmez); Mac ve Windows aynı kodla çalışır.

Eksileri: gecikme eşitleme servisine bağlı (genelde saniyeler, bazen dakikalar); kullanıcının bir
eşitleme aracı kurmuş olması gerekir; konu başlıkları ve ajan raporları o buluta yazılır
(kullanıcının kendi hesabı olsa da bu açıkça söylenmeli ve ayar varsayılan olarak kapalı olmalı).

### B. Bilgisayarların sunucuları doğrudan konuşur (yerel ağ / Tailscale)

Her sunucu, ayrı bir portta yalnızca okuma yapan bir `/peer/scan` ucu açar; bilgisayarlar bir
eşleştirme koduyla birbirine bağlanır, istekler paylaşılan gizli anahtarla imzalanır.

Artıları: gecikme yok; üçüncü bir servis yok.
Eksileri: ağda dinleyen bir port demek, güvenlik yüzeyi büyür (yanlış yapılandırmada konu
başlıkları yerel ağa açılır); aynı ağda olmayan bilgisayarlar için Tailscale gibi bir araç şart;
Windows güvenlik duvarı izin ister; otomatik bulma (Bonjour/mDNS) Python'da ek paket gerektirir,
yoksa adresler elle girilir. Kurulum, A'dan belirgin şekilde zor.

### C. Barındırılan eşitleme servisi (ileride ücretli "Pro" adayı)

Qosmopol sunucuları özetlerini uçtan uca şifreleyip küçük bir bulut aktarıcısına gönderir
(ör. Cloudflare Workers + KV); diğer bilgisayarlar ve **telefon** oradan okur.

Artıları: eşitleme aracı gerekmez; telefondan görme ve cevaplama yolu açılır; kopyalanan kodla
kullanılamayan, sürdürülebilir bir ücretli özellik olur.
Eksileri: altyapı, hesap, ödeme ve bakım işi; gizlilik sorumluluğu Qosmopol'a geçer (uçtan uca
şifreleme şart); en büyük iş bu.

### D. Claude'un Projects listesini uzak gezegen olarak göstermek

Elenmesi önerilir: listenin belgelenmiş bir arayüzü yok (uygulamanın iç deposu, her sürümde
değişebilir) ve yalnızca proje **adlarını** verir; asıl istenen bilgi olan bekleyen konular yine
görünmez.

## 4. Karşılaştırma

| | A. Ortak klasör | B. Doğrudan bağlantı | C. Bulut servisi | D. Projects listesi |
|---|---|---|---|---|
| Bekleyenleri her yerde görme | evet (gecikmeli) | evet | evet | hayır |
| Başka bilgisayara mesaj | 2. aşamada, kuyrukla | evet | evet | hayır |
| Telefondan görme | hayır | hayır | evet | hayır |
| Ağda açık port | yok | var | yok | yok |
| Ek kurulum | eşitleme klasörü seçmek | eşleştirme + çoğu zaman Tailscale | hesap | yok |
| Aylık maliyet | yok | yok | var | yok |
| İş büyüklüğü | küçük-orta | orta-büyük | büyük | küçük ama değersiz |

## 5. Öneri ve aşamalar

**A ile başla, C'yi ileride ücretli seçenek olarak düşün; B ve D yapılmasın.**

1. **Aşama 1 — salt okuma (0.2.0).**
   - Sunucu, ayar açıksa özetini ortak klasöre yazar ve diğer cihazların özetlerini `/api/scan`
     cevabına `devices` alanı olarak ekler; her uzak konu `dev` (cihaz kimliği) taşır.
   - Harita: uzak cihazların gezegenleri aynı gökyüzünde, adlarının altında küçük bir cihaz etiketiyle
     (ör. "· Windows"); kenar çubuğunda cihaz süzgeci; çevrimdışı cihaz soluk.
   - Sayaçlar ve yazma kutusunun üstündeki şerit: "3 bekliyor (+2 diğer bilgisayarda)".
   - Uzak konuya tıklayınca sütun açılır, son durum ve bekleyen soru gösterilir. Konuşma metni
     (`konu.py`) uzak bilgisayardan okunamadığı için bu aşamada yalnızca rapor satırları görünür.
   - "Uygulamada aç" uzak konuda gizlenir; yerine "claude.ai'de aç" çıkar (`https://claude.ai/code/<son
     bridgeSessionIds>`, doğrulandı). Bağlantı geçersizse claude.ai "bulunamadı" der; bunu harita
     önceden bilemez, düğmenin altında "Remote Control açıksa" notu yazar.
   - Bu sayede uzaktaki bir konuya 2. aşamayı beklemeden cevap verilebilir: claude.ai'de açılan konuda
     doğrudan yazılır.
2. **Aşama 2 — uzaktan işlem (0.3.0).**
   - Uzak konuya mesaj, kapatma, yeniden açma: iş, hedef cihazın `gelen/<cihaz-id>/` klasörüne bir
     dosya olarak bırakılır; hedef sunucu onu kendi kuyruğuna alır ve oradaki ana oturum köprüsü yapar.
   - Kötüye kullanıma karşı: her iş, eşleştirme sırasında yalnızca iki bilgisayarın yerel diskine
     yazılan (eşitlenen klasöre **yazılmayan**) bir anahtarla HMAC imzası taşır; imzasız ya da eski
     tarihli iş reddedilir.
   - Sonuç (`sonuc.json`) aynı yoldan geri döner.
3. **Aşama 3 — isteğe bağlı bulut (C).** Talep olursa; telefon görünümüyle birlikte "Pro" adayı.

## 6. Başlamadan önce doğrulanacaklar

1. ~~Remote Control kimliği claude.ai/code bağlantısıyla açılıyor mu?~~ **Doğrulandı (1 Kasım):**
   güncel Remote Control konularında açılıyor, eski konularda "bulunamadı" diyor (§2). Kalan soru:
   kimliğin ne zaman geçersiz olduğu (konu kapanınca mı, belli bir süre sonra mı).
2. iCloud Drive ve Google Drive'da küçük bir dosyanın Mac ↔ Mac ve Mac ↔ Windows arasında kaç
   saniyede eşitlendiği (her biri için 10 ölçüm).
3. Windows'ta iCloud Drive klasörünün varsayılan yolu ve eşitlenmemiş ("yalnızca bulutta")
   dosyaların okunurken indirilmesi.
4. Aynı Claude hesabının iki bilgisayarında `acc` (hesap kimliği) değerlerinin aynı olup olmadığı;
   arşivleme kuralı ("yalnızca o anki hesabın konusu") buna dayanıyor.

## 7. Dokunulacak dosyalar (Aşama 1)

- `bin/server.py`: ayar okuma, özet yazma ve uzak özetleri okuma, `/api/scan`'e `devices` ekleme,
  ayar için yeni bir `/api/sync` ucu.
- `bin/scan.py`: satırlara `bridge` (Remote Control kimliği) alanı.
- `web/index.html`: cihaz etiketi, cihaz süzgeci, sayaçların ayrılması, uzak sütunun sade hali,
  ayar ekranı.
- `hooks/register.tsx`: şeritte "(+N diğer bilgisayarda)".
- `tests/pane.test.tsx` ve sunucu için küçük bir Python testi: iki sahte cihaz dosyasıyla birleştirme,
  eski dosyanın çevrimdışı sayılması, ayar kapalıyken hiçbir dosya yazılmaması.
- `README.md`: ayarın ne yaptığı ve hangi verinin eşitlenen klasöre yazıldığı.
