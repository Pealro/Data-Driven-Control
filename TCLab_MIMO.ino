/*
 * ===========================================================================
 *  TCLab_MIMO.ino
 *  Sketch autonomo (Arduino IDE) que exercita CORRETAMENTE todas as entradas e
 *  saidas do modulo TCLab no modo MIMO (2 aquecedores + 2 sensores).
 *
 *  Alvo: Arduino LEONARDO (selecione a placa Leonardo na Arduino IDE). O
 *  Leonardo tem USB nativo, entao o setup() espera a porta conectar antes de
 *  anunciar READY (while(!Serial)); isso e inofensivo no Uno. Os pinos usados
 *  (D3, D5, D9 PWM; A0, A2 analogicos) existem e sao compativeis nas duas placas,
 *  e o shield TCLab (formato Uno) encaixa no Leonardo.
 *
 *  Pinagem OFICIAL do TCLab (shield APMonitor) -- confira com esta:
 *    Saidas PWM:
 *      Q1  (aquecedor 1) -> pino D3
 *      Q2  (aquecedor 2) -> pino D5
 *      LED (indicador)   -> pino D9
 *    Entradas analogicas (sensores de temperatura TMP36):
 *      T1  (sensor 1)    -> A0
 *      T2  (sensor 2)    -> A2      <-- ATENCAO: A2, NAO A1 (o TCLab pula o A1)
 *
 *  Isto corrige a divergencia do firmware do projeto (firmware/boards/tclab_mimo
 *  lia T2 em A1). O restante da calibracao segue o padrao TCLab: sensor TMP36
 *  (10 mV/C, offset 500 mV a 0 C) e AREF = 3,3 V vindo do shield, entao a leitura
 *  de fundo de escala e 3300 mV.
 *
 *  Protocolo serial (115200 baud, linhas ASCII):
 *    PC -> Arduino:
 *      Q1 <0..100>   define o duty do aquecedor 1 (%)
 *      Q2 <0..100>   define o duty do aquecedor 2 (%)
 *      LED <0..100>  define o brilho do LED (%)
 *      R             le e imprime uma amostra agora
 *      X             desliga tudo (Q1=Q2=LED=0)
 *    Arduino -> PC (a cada AMOSTRA):
 *      DATA,<t_ms>,<T1_C>,<T2_C>,<Q1_%>,<Q2_%>
 *  Alem disso, uma amostra e enviada automaticamente a cada 1 s.
 *
 *  Seguranca: se T1 ou T2 passar de T_SAFE, desliga tudo e avisa (ERR,OVERTEMP).
 * ===========================================================================
 */

// ------------------------------- pinos ------------------------------------
const int PIN_Q1  = 3;    // aquecedor 1 (PWM)
const int PIN_Q2  = 5;    // aquecedor 2 (PWM)
const int PIN_LED = 9;    // LED indicador (PWM)
const int PIN_T1  = A0;   // sensor de temperatura 1 (TMP36)
const int PIN_T2  = A2;   // sensor de temperatura 2 (TMP36)  <-- A2, correto

// --------------------------- calibracao TCLab -----------------------------
const float MV_FULLSCALE = 3300.0;  // AREF = 3,3 V (shield TCLab)
const float PMAX_Q       = 200.0;   // teto de potencia dos heaters (0..255), padrao TCLab
const float T_SAFE       = 100.0;   // limite de seguranca [C] -> desliga tudo
const unsigned long SAMPLE_INTERVAL_MS = 1000UL;

// ------------------------------- estado -----------------------------------
float duty_q1 = 0.0, duty_q2 = 0.0, duty_led = 0.0;
unsigned long last_sample_ms = 0;
char line_buffer[48];
byte line_len = 0;

// -------------------------- leitura de temperatura ------------------------
// TMP36: Vout = 10 mV/C com 500 mV a 0 C  ->  T[C] = (mV - 500) / 10.
// Media de 10 leituras para reduzir ruido (mesmo padrao do firmware do projeto).
float readTemp(int pin) {
  long acc = 0;
  for (int i = 0; i < 10; i++) acc += analogRead(pin);
  float millivolts = (acc / 10.0) * MV_FULLSCALE / 1024.0;
  return (millivolts - 500.0) / 10.0;
}

// ------------------------------ atuadores ---------------------------------
void applyHeaters() {
  analogWrite(PIN_Q1, (int)(constrain(duty_q1, 0.0, 100.0) * PMAX_Q / 100.0 + 0.5));
  analogWrite(PIN_Q2, (int)(constrain(duty_q2, 0.0, 100.0) * PMAX_Q / 100.0 + 0.5));
  analogWrite(PIN_LED, (int)(constrain(duty_led, 0.0, 100.0) * 255.0 / 100.0 + 0.5));
}

void allOff() {
  duty_q1 = duty_q2 = duty_led = 0.0;
  analogWrite(PIN_Q1, 0);
  analogWrite(PIN_Q2, 0);
  analogWrite(PIN_LED, 0);
}

// ------------------------------ amostra -----------------------------------
void sendSample() {
  float t1 = readTemp(PIN_T1);
  float t2 = readTemp(PIN_T2);
  if (t1 > T_SAFE || t2 > T_SAFE) {
    allOff();
    Serial.print(F("ERR,OVERTEMP,"));
    Serial.print(t1, 2); Serial.print(F(",")); Serial.println(t2, 2);
    return;
  }
  Serial.print(F("DATA,"));
  Serial.print(millis());               Serial.print(F(","));
  Serial.print(t1, 2);                  Serial.print(F(","));
  Serial.print(t2, 2);                  Serial.print(F(","));
  Serial.print(duty_q1, 1);             Serial.print(F(","));
  Serial.println(duty_q2, 1);
}

// ------------------------- parser de comandos -----------------------------
void handleLine(char *line) {
  // separa "CMD" e o resto (valor)
  char *cmd = strtok(line, " ");
  if (cmd == NULL) return;
  char *arg = strtok(NULL, " ");
  float value = (arg != NULL) ? atof(arg) : 0.0;

  if (strcasecmp(cmd, "Q1") == 0)       { duty_q1 = constrain(value, 0.0, 100.0);  applyHeaters(); }
  else if (strcasecmp(cmd, "Q2") == 0)  { duty_q2 = constrain(value, 0.0, 100.0);  applyHeaters(); }
  else if (strcasecmp(cmd, "LED") == 0) { duty_led = constrain(value, 0.0, 100.0); applyHeaters(); }
  else if (strcasecmp(cmd, "R") == 0)   { sendSample(); }
  else if (strcasecmp(cmd, "X") == 0)   { allOff(); Serial.println(F("OK,OFF")); }
  else                                  { Serial.print(F("ERR,CMD,")); Serial.println(cmd); }
}

// -------------------------------- setup/loop ------------------------------
void setup() {
  pinMode(PIN_Q1, OUTPUT);
  pinMode(PIN_Q2, OUTPUT);
  pinMode(PIN_LED, OUTPUT);
  allOff();
  Serial.begin(115200);
  // Leonardo (USB nativo): espera a porta conectar; no Uno sai na hora.
  unsigned long start = millis();
  while (!Serial && (millis() - start) < 5000UL) {}
  Serial.println(F("TCLAB-MIMO,READY"));
}

void loop() {
  // 1) le comandos do serial (nao bloqueante, uma linha por vez)
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      if (line_len > 0) { line_buffer[line_len] = '\0'; handleLine(line_buffer); line_len = 0; }
    } else if (line_len < sizeof(line_buffer) - 1) {
      line_buffer[line_len++] = c;
    }
  }
  // 2) amostra automatica a cada SAMPLE_INTERVAL_MS
  unsigned long now = millis();
  if (now - last_sample_ms >= SAMPLE_INTERVAL_MS) {
    last_sample_ms = now;
    sendSample();
  }
}
