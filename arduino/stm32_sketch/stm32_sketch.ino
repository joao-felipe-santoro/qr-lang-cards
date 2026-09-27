/*
 * Leitor de Cartas Trilíngue — STM32 sketch (Arduino UNO Q)
 * ===========================================================
 * Lê IDs de QR Code do GM65 via UART1 e repassa ao lado Linux
 * via Serial (App Lab Bridge).
 *
 * Também controla o LED RGB de feedback via GPIO.
 *
 * Pinagem GM65 → UNO Q:
 *   GM65 VCC  → 5V
 *   GM65 GND  → GND
 *   GM65 TX   → D0 (RX1 do STM32)
 *   GM65 RX   → D1 (TX1 do STM32)
 *
 * LED RGB (anodo comum — ajuste lógica se for catodo comum):
 *   R → D9  (via resistor 220Ω)
 *   G → D10 (via resistor 220Ω)
 *   B → D11 (via resistor 220Ω)
 *
 * Baud rate: 9600 (GM65 padrão de fábrica)
 */

// ── Pinos ──────────────────────────────────────────────────────────────────
#define LED_R   9
#define LED_G   10
#define LED_B   11

// ── Constantes ─────────────────────────────────────────────────────────────
#define BAUD_GM65    9600
#define BAUD_BRIDGE  9600

// Tempo mínimo entre duas leituras do mesmo QR (ms)
#define COOLDOWN_MS  2500

// ── Variáveis ──────────────────────────────────────────────────────────────
String ultimoQR     = "";
unsigned long ultimoMs = 0;

// ── Setup ──────────────────────────────────────────────────────────────────
void setup() {
  // Serial → App Lab Bridge (lado Linux)
  Serial.begin(BAUD_BRIDGE);

  // Serial1 → GM65
  Serial1.begin(BAUD_GM65);

  // LED
  pinMode(LED_R, OUTPUT);
  pinMode(LED_G, OUTPUT);
  pinMode(LED_B, OUTPUT);
  ledOff();

  // Pisca azul 2x na inicialização
  for (int i = 0; i < 2; i++) {
    ledSet(0, 0, 1);
    delay(200);
    ledOff();
    delay(150);
  }

  Serial.println("READY");   // sinaliza ao Linux que o sketch está ativo
}

// ── Loop principal ─────────────────────────────────────────────────────────
void loop() {
  // Lê linha completa enviada pelo GM65 (termina em \r\n ou \n)
  if (Serial1.available()) {
    String qr = Serial1.readStringUntil('\n');
    qr.trim();   // remove \r e espaços

    if (qr.length() == 0) return;

    unsigned long agora = millis();

    // Filtra leituras repetidas dentro do cooldown
    if (qr == ultimoQR && (agora - ultimoMs) < COOLDOWN_MS) {
      return;
    }

    ultimoQR = qr;
    ultimoMs = agora;

    // Repassa o ID ao Linux via Bridge
    Serial.println(qr);

    // Feedback visual: verde = leitura OK
    ledOK();
  }

  // Verifica se o lado Linux enviou um comando de feedback
  // Protocolo: "ERR\n" → LED vermelho, "OK\n" → LED verde
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    if (cmd == "ERR")  ledErro();
    else if (cmd == "OK") ledOK();
  }
}

// ── Funções de LED ─────────────────────────────────────────────────────────

// Define cor do LED (true = aceso)
// ATENÇÃO: para LED anodo comum inverta a lógica (LOW = aceso)
void ledSet(bool r, bool g, bool b) {
  digitalWrite(LED_R, r ? HIGH : LOW);
  digitalWrite(LED_G, g ? HIGH : LOW);
  digitalWrite(LED_B, b ? HIGH : LOW);
}

void ledOff() {
  ledSet(0, 0, 0);
}

// Verde rápido → leitura bem-sucedida
void ledOK() {
  ledSet(0, 1, 0);
  delay(300);
  ledOff();
}

// Vermelho → ID desconhecido
void ledErro() {
  ledSet(1, 0, 0);
  delay(500);
  ledOff();
}
