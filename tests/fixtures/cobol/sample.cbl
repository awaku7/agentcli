       IDENTIFICATION DIVISION.
       PROGRAM-ID. SAMPLE-PROGRAM.
       AUTHOR. TEST.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-NAME    PIC X(30).
       01  WS-AGE     PIC 9(3).
       01  WS-RESULT  PIC X(100).
       PROCEDURE DIVISION.
       MAIN-PARA.
           DISPLAY "Starting program".
           PERFORM INIT-PARA
           PERFORM PROCESS-PARA
           STOP RUN.
       INIT-PARA.
           MOVE "John" TO WS-NAME
           MOVE 30 TO WS-AGE.
       PROCESS-PARA.
           STRING "Hello, " DELIMITED BY SIZE
                  WS-NAME DELIMITED BY SPACE
                  " aged " WS-AGE
                  INTO WS-RESULT
           END-STRING
           DISPLAY WS-RESULT.
