/*
	<Pico-10DOF-IMU main source file.>
	Copyright (C) <2021>  <Waveshare team>

	This program is free software: you can redistribute it and/or modify
	it under the terms of the GNU General Public License as published by
	the Free Software Foundation, either version 3 of the License, or
	(at your option) any later version.

	This program is distributed in the hope that it will be useful,
	but WITHOUT ANY WARRANTY; without even the implied warranty of
	MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
	GNU General Public License for more details.

	You should have received a copy of the GNU General Public License
	along with this program.  If not, see <https://www.gnu.org/licenses/>.
*/
#include "icm20948.h"
#include "lps22hb.h"
#include <stdio.h>
#include "pico/stdlib.h"

int main(void)
{
	stdio_init_all();
	IMU_EN_SENSOR_TYPE enMotionSensorType;
	IMU_ST_ANGLES_DATA stAngles;
	IMU_ST_SENSOR_DATA stGyroRawData;
	IMU_ST_SENSOR_DATA stAccelRawData;
	IMU_ST_SENSOR_DATA stMagnRawData;
    float PRESS_DATA=0;
    float TEMP_DATA=0;
    uint8_t u8Buf[3];
	imuInit(&enMotionSensorType);
	if(IMU_EN_SENSOR_TYPE_ICM20948 == enMotionSensorType)
	{
		printf("Motion sersor is ICM-20948\n" );
	}
	else
	{
		printf("Motion sersor NULL\n");
	}
	if (!LPS22HB_INIT()){
		printf("LPS22HB Init Error\n");
		return 0;
	}
	while(1){
		LPS22HB_START_ONESHOT();
        /*
        if((I2C_readByte(LPS_STATUS)&0x01)==0x01)   //a new pressure data is generated
        {
            u8Buf[0]=I2C_readByte(LPS_PRESS_OUT_XL);
            u8Buf[1]=I2C_readByte(LPS_PRESS_OUT_L);
            u8Buf[2]=I2C_readByte(LPS_PRESS_OUT_H);
            PRESS_DATA=(float)((u8Buf[2]<<16)+(u8Buf[1]<<8)+u8Buf[0])/4096.0f;
        }
        if((I2C_readByte(LPS_STATUS)&0x02)==0x02)   // a new pressure data is generated
        {
            u8Buf[0]=I2C_readByte(LPS_TEMP_OUT_L);
            u8Buf[1]=I2C_readByte(LPS_TEMP_OUT_H);
            TEMP_DATA=(float)((u8Buf[1]<<8)+u8Buf[0])/100.0f;
        }
        */
	imuDataGet( &stAngles, &stGyroRawData, &stAccelRawData, &stMagnRawData);
	printf("\r\n {");
	printf("\"roll\":%.2f, \"pitch\":%.2f, \"yaw\":%.2f",stAngles.fRoll, stAngles.fPitch, stAngles.fYaw);
	//printf(", ");
	//printf("\"pressure\":%6.2f, \"temperature\":%6.2f, ", PRESS_DATA, TEMP_DATA); //in hPa and degrees Celsius respectively
	//printf(", ");
	//printf("\"accel_x\":%d, \"accel_y\":%d, \"accel_z\":%d, ",stAccelRawData.s16X, stAccelRawData.s16Y, stAccelRawData.s16Z);
	//printf(", ");
	//printf("\"gyro_x\":%d, \"gyro_y\":%d, \"gyro_z\":%d, ",stGyroRawData.s16X, stGyroRawData.s16Y, stGyroRawData.s16Z);
	//printf(", ");
	//printf("\"magno_x\":%d, \"magno_y\":%d, \"magno_z\":%d, ",stMagnRawData.s16X, stMagnRawData.s16Y, stMagnRawData.s16Z);
	printf("}");
	sleep_ms(100);
	}
		return 0;
}
