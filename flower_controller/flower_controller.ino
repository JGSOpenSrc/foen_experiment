#include "avr/interrupt.h"

#define INJECTION_TRIGGER_PIN 5
#define INJECTION_DELAY 10
#define INJECTOR_RST_PIN 4
#define LIQUID_SENSE_PIN 0x03 // Pin A3
#define ACCEL_X_PIN 0x02      // Pin A2
#define ACCEL_Y_PIN 0x01      // Pin A1
#define ACCEL_Z_PIN 0x00      // Pin A0
#define DEBUG_PIN 2

#define LOW_TO_HIGH 150
#define HIGH_TO_LOW 75

#define BUFFER_LEN 256

#define SYS_CLK_FREQ 16000000

bool stopflag = false;                                          // Emertency stop flag that is set by the forward limit switch. Prevents damage to syringe.
bool reset = true;                                              // Reset flag used to initiali1ze the position of the injector.
bool sampleNectar = false;
bool isEmpty;
bool debugFlag;

unsigned int tbase1_freq;
unsigned int tbase2_freq;
unsigned int tbase3_freq = 1;
unsigned int timer1_timeout;
unsigned int tbase1 = 0;                                        // Counter variable, increments at SYS_TBASE1_FREQ
unsigned int tbase2 = 0;                                        // Counter variable, increments at SYS_TBASE2_FREQ
unsigned int tbase3 = 0;                                        // Counter variable, increments at SYS_TBASE3_FREQ
unsigned int lastTime1 = 0;                                     // lastTime variables update each time loop() sees a change in tbase
unsigned int lastTime2 = 0;
unsigned int lastTime3 = 0;
unsigned int tLatch1 = 0;                                       // tLatch variables are used to implement time delays
unsigned int tLatch2 = 0;
unsigned int tLatch3 = 0;

int x = 0; 
int y = 0; 
int z = 0;
int irVal = 0;
char input_buffer[BUFFER_LEN];                                  // Serial input buffer, used to store serial data and to parse commands.
char output_buffer[BUFFER_LEN];                                 // Serial output buffer, used to store messages which will be sent out to the serial port.
char* cmd;                                                      // String pointer, used to parse serial commands
char* value;                                                    // String pointer, used to parse serial commands

void tick(void);
void injection(void);
void sampleAccelerometer();
void sendAccelData();
void sampleNectarVolume();
void sendNectarData();
void determineFlowerState();

void setup() {
  
  // initialize message buffer
  int i;

  // Setup Serial Port to run at 1MHz
  UART_INIT(0x01);
  
  // Initialize the IO ports
  IO_INIT();
  
  // Iinitialize analog to digital conversion
  ADC_INIT();

  // Initialize motor
  int avg = 0;                                                  // Initialize Nectar container state
  for(i = 0; i < 10; i++){
    avg += analogRead(LIQUID_SENSE_PIN);
  }
  if (LOW_TO_HIGH < (avg / 10)){
    isEmpty = true;
    Serial.println("Container is initially empty");
    sprintf(output_buffer, "average value read is %d", avg / 10);
    Serial.println(output_buffer);
  }
  else if (HIGH_TO_LOW > (avg / 10)){
    isEmpty = false;
    Serial.println("Container is initially full");
    sprintf(output_buffer, "average value read is %d", avg / 10);
    Serial.println(output_buffer);
  } 
  else {
    Serial.println("Container state unknown!");
    sprintf(output_buffer, "average value read is %d", avg / 10);
    Serial.println(output_buffer);
    //while(1);                                                    // Loop forever, something is wrong!
  }

  int exitcode = 0;
  /* Wait for accellerometer sample rate */
  do {
    exitcode = getcmd(input_buffer);
  } while(0 != exitcode);
  tbase1_freq = 4 * atoi(input_buffer);
  
  /* Wait for nectar sample rate */;
  do{
    exitcode = getcmd(input_buffer);
  } while(0 != exitcode);
  tbase2_freq = atoi(input_buffer);

  // Initialize Counter 1, used to synchronize tasks
  timer1_timeout = SYS_CLK_FREQ / (1 * tbase1_freq) - 1;          // Timeout value is used to set sampling rate
  TIMER_INIT(timer1_timeout);
  debugFlag = false;  
  sei();                                                          // Enable interrupts
}

ISR(TIMER1_COMPA_vect) {
  cli();
  TCNT1 = 0;
  TIFR1 |= 0xFF;
  tbase1++;
  if(tLatch1 + (tbase1_freq / tbase2_freq) == tbase1){
    tLatch1 = tbase1;
    tbase2++;
    if(tLatch2 + (tbase2_freq / tbase3_freq) == tbase2){
      tLatch2 = tbase2;
      tbase3++;
    }
  }
  sei();
}

/* This function initializes the UART. It configures the data frame for 8-bits,
1 stop bit, and no parity. The baudrate is adjusted by setting the double speed
bit (U2X0). The effective baudrate is 16MHz/8/(ubrr+1). 
*/
void UART_INIT(unsigned int ubrr){
  Serial.begin(9600);
  /* Set Baud Rate */
  UBRR0H = (unsigned char)(ubrr>>8);
  UBRR0L = (unsigned char)(ubrr);
  /* Put into double mode */
  UCSR0A |= (1<<U2X0);
}

void IO_INIT(){
  // Used to trigger microinjector
  pinMode(INJECTION_TRIGGER_PIN, OUTPUT);
  digitalWrite(INJECTION_TRIGGER_PIN, HIGH);
  
  // Used to force the injector into reset
  pinMode(INJECTOR_RST_PIN, OUTPUT);
  digitalWrite(INJECTOR_RST_PIN, LOW);
  delay(1);
  digitalWrite(INJECTOR_RST_PIN, HIGH);
  
  // Used to measure the system frequency
  pinMode(DEBUG_PIN, OUTPUT);

  // Pins for A/D sampling
  pinMode(LIQUID_SENSE_PIN, INPUT);
  pinMode(ACCEL_X_PIN, INPUT);
  pinMode(ACCEL_Y_PIN, INPUT);
  pinMode(ACCEL_Z_PIN, INPUT);
}

/* This function initializes the 16-bit timer / counter that is used
to set the frequency of the system time base. This subsequently affects
the sampling frequency of the data, and the duration of the nectar injection
delay. You probably won't have to change any of this code. If you wish to adjust the
frequency of the system, simply change the TIMER1_TIMEOUT function.
*/
void TIMER_INIT(unsigned int timeout){
  TCCR1A = 0x00;                                                // Configure the timer to run in normal mode                                        
  TCCR1B = (1<<CS10);
  TIMSK1 = 0;
  TIMSK1 |= (1<<OCIE1A);                                        // Enable output compare interrupt
  TCNT1 = 0;
  OCR1A = timeout;                                              // Set the value of the output compare register
  TCNT1 = 0;                                                    // Reset the counter
  TIFR1 |= 0xFF;                                                // Reset the output compare interrupt flag
}

/* This function initializes the analog to digital converter.
If a different configuration is required, consult the atmega328p 
datasheet under the ADC chapter */
void ADC_INIT(){
  ADCSRA &= 0x00;
  ADCSRA |= (1<<ADEN)|(1<<ADPS2)|(1<<ADPS1)|(1<<ADPS0);         // Enables converter, sets clock to 250KHz
  ADMUX |= (1<<REFS0);                                          // Sets channel to A0 and voltage ref to VCC
  ADCSRA |= (1<<ADSC);                                          // Do an intial conversion, and throw it out
  while(ADCSRA & (1<<ADSC));                                    // Wait for conversion to complete
}
/*
 * Get command is used to read data from the serial port into the input_buffer string.
 * It reads from the serial port until a newline terminator is found.
 * Exit code 0:  success
 * Exit code 1:  no data avaialable
 * Exit code -1: buffer overflow 
 */
int getcmd(char* input_buffer){
  int exitcode;
  bool done = false;
  char* ptr = input_buffer;
  if(!Serial.available()){                                        // No data avialable, return exit code 1.
    exitcode = 1; 
  } 
  else {
    while(!done){                                                 // Read bytes until null terminator received.
      if(Serial.available()){
        *ptr = Serial.read();
        if('\n' == *ptr){
          *ptr = '\0';
          done = true;
          exitcode = 0;
        }
        ptr++;
      } 
      if(input_buffer + BUFFER_LEN < ptr){
        done = true;
        exitcode = -1;
      }
    }
  }
  return exitcode;
}

void sample_send_x();
void sample_send_y();
void sample_send_z();
void sample_send_n();
void check_volume();
void inject();

void loop() {
 if(tbase1 != lastTime1){
   lastTime1 = tbase1;
   PIND |= (1<<PIND2);
   sample_send_x();
   sample_send_y();
   sample_send_z();
   sample_send_n();
   check_volume();
   inject();
  }
}

void sample_send_x(){
  // Sample and send
  if(0==(tbase1 % 4)){
    // Sample x-pin
    ADMUX = (1<<REFS0) | (1<<ADLAR) | ACCEL_X_PIN;
    ADCSRA |= (1<<ADSC);
    while(ADCSRA & (1<<ADSC));
    
    // Send code for X DATA
    UDR0 = 'X';
    while(!(UCSR0A&(1<<TXC0)));
    UCSR0A |= (1<<TXC0);
    
    // Send value read on x pin
    UDR0 = ADCH;
    while(!(UCSR0A&(1<<TXC0)));
    UCSR0A |= (1<<TXC0);
    
    // Send time stamp
    UDR0 = (unsigned char)tbase1;
    while(!(UCSR0A&(1<<TXC0)));
    UCSR0A |= (1<<TXC0);
    
    // Send stop byte
    UDR0 = '\n';
    while(!(UCSR0A&(1<<TXC0)));
    UCSR0A |= (1<<TXC0);
  }
}
void sample_send_y(){
  if(1 == (tbase1 % 4)){
    // Sample y-pin
    ADMUX = (1<<REFS0) | (1<<ADLAR) | ACCEL_Y_PIN;
    ADCSRA |= (1<<ADSC);
    while(ADCSRA & (1<<ADSC));
    
    // Send code for Y DATA
    UDR0 = 'Y';
    while(!(UCSR0A&(1<<TXC0)));
    UCSR0A |= (1<<TXC0);
    
    // Send value read on x pin
    UDR0 = ADCH;
    while(!(UCSR0A&(1<<TXC0)));
    UCSR0A |= (1<<TXC0);
    
    // Send time stamp
    UDR0 = (unsigned char)tbase1;
    while(!(UCSR0A&(1<<TXC0)));
    UCSR0A |= (1<<TXC0);
    
    // Send stop byte
    UDR0 = '\n';
    while(!(UCSR0A&(1<<TXC0)));
    UCSR0A |= (1<<TXC0);
  }
}
void sample_send_z(){
   if(2 == (tbase1 % 4)){
    // Sample Z-pin
    ADMUX = (1<<REFS0) | (1<<ADLAR) | ACCEL_Z_PIN;
    ADCSRA |= (1<<ADSC);
    while(ADCSRA & (1<<ADSC));
    
    // Send code for X DATA
    UDR0 = 'Z';
    while(!(UCSR0A&(1<<TXC0)));
    UCSR0A |= (1<<TXC0);
    
    // Send value read on x pin
    UDR0 = ADCH;
    while(!(UCSR0A&(1<<TXC0)));
    UCSR0A |= (1<<TXC0);
    
    // Send time stamp
    UDR0 = (unsigned char)tbase1;
    while(!(UCSR0A&(1<<TXC0)));
    UCSR0A |= (1<<TXC0);
    
    // Send stop byte
    UDR0 = '\n';
    while(!(UCSR0A&(1<<TXC0)));
    UCSR0A |= (1<<TXC0);
  }
}
void sample_send_n(){
  if(3 == (tbase1 % 4) && (tbase2 != lastTime2)){
    if(!(tbase2 % tbase3_freq)){
      sampleNectar = false;
      // Sample nectar
      ADMUX = (1<<REFS0) | (1<<ADLAR) | LIQUID_SENSE_PIN;
      ADCSRA |= (1<<ADSC);
      while(ADCSRA & (1<<ADSC));
      
      // Send code for N DATA
      UDR0 = 'N';
      while(!(UCSR0A&(1<<TXC0)));
      UCSR0A |= (1<<TXC0);
      
      // Send value read on nectar pin
      irVal = ADCH;
      UDR0 = irVal;
      while(!(UCSR0A&(1<<TXC0)));
      UCSR0A |= (1<<TXC0);
      
      // Send time stamp
      UDR0 = (unsigned char)tbase2;
      while(!(UCSR0A&(1<<TXC0)));
      UCSR0A |= (1<<TXC0);
    
      // Send stop byte
      UDR0 = '\n';
      while(!(UCSR0A&(1<<TXC0)));
      UCSR0A |= (1<<TXC0);
    }
  }
}
void check_volume(){
  if((3 == tbase1 % 4) && (tbase2 != lastTime2)){
    lastTime2 = tbase2;
    if(!isEmpty && (irVal > LOW_TO_HIGH)){ 
      isEmpty = true;
      tLatch3 = tbase3;
      // Code for nectar volume event
      UDR0 = 'E';
      while(!(UCSR0A&(1<<TXC0)));
      UCSR0A |= (1<<TXC0);
      
      // Send 0 signalling empty
      UDR0 = 0;
      while(!(UCSR0A&(1<<TXC0)));
      UCSR0A |= (1<<TXC0);
      
      // Send timestamp
      UDR0 = (unsigned char)tbase3;
      while(!(UCSR0A&(1<<TXC0)));
      UCSR0A |= (1<<TXC0);
      
      // Send stop byte
      UDR0 = '\n';
      while(!(UCSR0A&(1<<TXC0)));
      UCSR0A |= (1<<TXC0);
    }
    else if (isEmpty && (irVal < HIGH_TO_LOW)){
      isEmpty = false;
      // Code for nectar volume event
      UDR0 = 'E';
      while(!(UCSR0A&(1<<TXC0)));
      UCSR0A |= (1<<TXC0);
      
      // Send 0 signalling full
      UDR0 = 1;
      while(!(UCSR0A&(1<<TXC0)));
      UCSR0A |= (1<<TXC0);
      
      // Send timestamp
      UDR0 = (unsigned char)tbase3;
      while(!(UCSR0A&(1<<TXC0)));
      UCSR0A |= (1<<TXC0);
      
      // Send stop byte
      UDR0 = '\n';
      while(!(UCSR0A&(1<<TXC0)));
      UCSR0A |= (1<<TXC0);
    }
  }
}
void inject(){
  if((3 == tbase1 % 4)){
     if(tbase3 != lastTime3){
       lastTime3 = tbase3;
       if (isEmpty && (tbase3 == tLatch3 + INJECTION_DELAY)) {
        // Request injection from microinjector
        digitalWrite(INJECTION_TRIGGER_PIN, LOW);
        digitalWrite(INJECTION_TRIGGER_PIN, HIGH);
        tLatch3 = tbase3;
        
        //Send injection event code
        UDR0 = 'I';
        while(!(UCSR0A&(1<<TXC0)));
        UCSR0A |= (1<<TXC0);
        
        // Send null byte
        UDR0 = 0x00;
        while(!(UCSR0A&(1<<TXC0)));
        UCSR0A |= (1<<TXC0);
        
        // Send time stamp
        UDR0 = (unsigned char)tbase3;
        while(!(UCSR0A&(1<<TXC0)));
        UCSR0A |= (1<<TXC0);
        
        // Send stop byte
        UDR0 = '\n';
        while(!(UCSR0A&(1<<TXC0)));
        UCSR0A |= (1<<TXC0);
      }
    }
  }
}


