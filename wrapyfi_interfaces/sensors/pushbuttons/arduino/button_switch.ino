const int LED = 10;
const int LED2 = 11;
const int BUTTON = 9;
const int BUTTONB = 8;
boolean lastButton = LOW;
boolean lastButtonb = LOW;
boolean currentButton = LOW;
boolean currentButtonb = LOW;
boolean ledOn = false;
boolean ledOnb = false;
int incomingByte = 0;

void setup()
{
  Serial.begin(115200);
  pinMode (LED, OUTPUT);
  pinMode (LED2, OUTPUT);
  pinMode (BUTTON, INPUT);
  pinMode (BUTTONB, INPUT);
}

boolean debounce(boolean last)
{
  boolean current = digitalRead(BUTTON);
   if (last != current)
   {
     delay(1);
     current = digitalRead(BUTTON);
   }
    return current;
}

boolean debounceb(boolean lastb)
{
  boolean currentb = digitalRead(BUTTONB);
   if (lastb != currentb)
   {
     delay(1);
     currentb = digitalRead(BUTTONB);
   }
    return currentb;
}

void loop()
{
  // while (!Serial.available());  // remove this line to make the arduino function like a normal button switch
  currentButton = debounce(lastButton);
   if (lastButton == LOW && currentButton == HIGH)
   {
     ledOn = !ledOn;
   }
   lastButton = currentButton;

   digitalWrite(LED, ledOn);

   currentButtonb = debounceb(lastButtonb);
   if (lastButtonb == LOW && currentButtonb == HIGH)
   {
     ledOnb = !ledOnb;
   }
   lastButtonb = currentButtonb;

   digitalWrite(LED2, ledOnb);

   // send data only when you receive data:
   if (Serial.available() > 0) {
    // read the incoming byte:
    incomingByte = Serial.readString().toInt();
    if (incomingByte == 48){
      ledOn = false;
      digitalWrite(LED, ledOn);
      }
    if (incomingByte == 49){
      ledOn = true;
      digitalWrite(LED, ledOn);
      }
    if (incomingByte == 50){
      ledOnb = false;
      digitalWrite(LED2, ledOnb);
      }
    if (incomingByte == 51){
      ledOnb = true;
      digitalWrite(LED2, ledOnb);
      }

    Serial.println("{\"LED2\": " + String(ledOnb) + ", \"LED1\": " + String(ledOn) + "}");

    //Serial.println("{\"RCVD\": ");
    //Serial.println(incomingByte, DEC);
    //Serial.println("}");
  }
   delay(1);
}
