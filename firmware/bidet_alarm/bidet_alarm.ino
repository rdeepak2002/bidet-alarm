// Bidet alarm - beeps if the bidet T-valve is left open for 10 minutes.
//
// Wiring (Arduino Nano):
//   Reed sensor  -> D2 and GND   (no polarity, internal pull-up used)
//   Buzzer +     -> D8,  Buzzer - -> GND   (12 mm 5 V ACTIVE buzzer, <30 mA, safe to drive from a pin)
//
// Knob closed: magnet next to the reed switch -> switch closed -> D2 reads LOW.
// Knob open:   magnet swings away -> switch open -> D2 reads HIGH -> timer starts.

const int SWITCH_PIN = 2;
const int BUZZER_PIN = 8;

// MC-38 sensors sold as "NC" close when the magnet is near (what this design expects).
// If yours is sold as "NO" (opens when the magnet is near), set this to true.
const bool SENSOR_IS_NO = false;

const unsigned long ALARM_DELAY  = 10UL * 60UL * 1000UL; // 10 minutes (use 10UL * 1000UL while testing)
const unsigned long REPEAT_EVERY = 30UL * 1000UL;        // repeat the alarm every 30 s until closed

// Active buzzer: it makes its own ~2.3 kHz tone, so HIGH = sound, LOW = silent.
const int BEEPS = 6, BEEP_ON_MS = 200, BEEP_OFF_MS = 120;

unsigned long openedAt = 0;
unsigned long lastAlarm = 0;
bool wasOpen = false;

void setup() {
  pinMode(SWITCH_PIN, INPUT_PULLUP);
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(LED_BUILTIN, OUTPUT);
  Serial.begin(9600);
  // Short chirp on power-up so you know it's alive.
  digitalWrite(BUZZER_PIN, HIGH); delay(60); digitalWrite(BUZZER_PIN, LOW);
}

bool bidetIsOpen() {
  bool switchOpen = digitalRead(SWITCH_PIN) == HIGH;
  return SENSOR_IS_NO ? !switchOpen : switchOpen;
}

void playAlarm() {
  for (int i = 0; i < BEEPS; i++) {
    digitalWrite(BUZZER_PIN, HIGH); delay(BEEP_ON_MS);
    digitalWrite(BUZZER_PIN, LOW);  delay(BEEP_OFF_MS);
  }
}

void loop() {
  bool open = bidetIsOpen();
  unsigned long now = millis();

  if (open && !wasOpen) {          // just opened: start the timer
    openedAt = now;
    lastAlarm = 0;
  }

  if (open && now - openedAt >= ALARM_DELAY) {
    if (lastAlarm == 0 || now - lastAlarm >= REPEAT_EVERY) {
      playAlarm();
      lastAlarm = now;
    }
  }

  // Setup aid: the Nano's built-in LED is ON while the valve reads OPEN.
  // With the knob closed it must be OFF; if not, move the sensor closer to the magnet.
  digitalWrite(LED_BUILTIN, open ? HIGH : LOW);
  if (open != wasOpen) Serial.println(open ? "valve OPEN" : "valve CLOSED");

  wasOpen = open;
  delay(200);                      // also debounces the switch
}
