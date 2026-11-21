// Bidet alarm - beeps if the bidet T-valve is left open for 10 minutes.
//
// Wiring (Arduino Nano):
//   Reed sensor  -> D2 and GND   (no polarity, internal pull-up used)
//   Buzzer +     -> D8,  Buzzer - -> GND   (12 mm PASSIVE buzzer)
//
// Knob closed: magnet next to the reed switch -> switch closed -> D2 reads LOW.
// Knob open:   magnet swings away -> switch open -> D2 reads HIGH -> timer starts.

const int SWITCH_PIN = 2;
const int BUZZER_PIN = 8;

const unsigned long ALARM_DELAY  = 10UL * 60UL * 1000UL; // 10 minutes (use 10UL * 1000UL while testing)
const unsigned long REPEAT_EVERY = 30UL * 1000UL;        // repeat the alarm every 30 s until closed

// Small piezo buzzers are loudest near their resonant frequency (usually ~2.3-2.7 kHz,
// check your buzzer's listing). Alternating around it sounds urgent and stays loud.
const int TONE_HIGH = 2700;
const int TONE_LOW  = 2300;

unsigned long openedAt = 0;
unsigned long lastAlarm = 0;
bool wasOpen = false;

void setup() {
  pinMode(SWITCH_PIN, INPUT_PULLUP);
  pinMode(BUZZER_PIN, OUTPUT);
  // Short chirp on power-up so you know it's alive.
  tone(BUZZER_PIN, TONE_HIGH, 80);
}

bool bidetIsOpen() {
  return digitalRead(SWITCH_PIN) == HIGH;
}

void playAlarm() {
  for (int i = 0; i < 4; i++) {
    tone(BUZZER_PIN, TONE_HIGH, 250); delay(300);
    tone(BUZZER_PIN, TONE_LOW, 250);  delay(300);
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

  wasOpen = open;
  delay(200);                      // also debounces the switch
}
