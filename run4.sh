#!/bin/bash

#xterm -hold -e  "echo 1;echo 1;echo 1;" &

for number_request in 100 1000 3000 5000 10000;
do
	#Starting time counting
	START=$(date +%s)
		for count_request in $(seq $number_request);
		do
			curl 10.0.1.1 #making request
		done    
    END=$(date +%s)
    #Ending time counting
    Time_Resquest=$(($END - $START)) 
    echo "Time $Time_Resquest for $count_request requisitions" >> results4.txt
done 