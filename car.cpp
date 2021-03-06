#include "car.h"
#include <Wire.h>
#include <I2Cdev.h>
#include "Wheel.h"
#include "CarStates.h"
#include <Arduino.h>

#define PI 3.14159265

Car::Car():
    ud_start_time(millis()),
    distance_cm(0.f),
    wheel_left(LEFT_WHEEL_FORWARD_PIN, LEFT_WHEEL_BACKWARD_PIN),
    wheel_right(RIGTH_WHEEL_FORWARD_PIN, RIGTH_WHEEL_BACKWARD_PIN),
    ultrasonic(US_TRIGER_PIN, US_ECHO_PIN, US_MAX_DURATION_MK),
    last_cmd_time(0),
    check_last_time(false),
    enable_walk(false),
    max_walk_power(0.5),
    min_distance(20),
    show_info(false),
    info_period(100000)
{ 
    move_forward_state = new MoveForwardState(*this, 0.8, 15.f);
    turn_state = new TurnState(*this,  800000, 15.f, 0.7);
    move_back_state = new MoveBackState(*this, 800000, 0.7);
    turn_angle_state = new TurnAngleState(*this, PI/180. * 160., PI/180. * 4, 0.45, 0.3);
    //turn_angle_state = new TurnAngleState(*this, PI/180. * 120., PI/180. * 4, 1, 0.5);
   
    cur_state = move_forward_state;
    giro_angles[0] = 0.f;
    giro_angles[1] = 0.f;
    giro_angles[2] = 0.f;
}

Car::~Car()
{
    delete move_forward_state;
    delete turn_state;
    delete move_back_state;
}


void Car::update()
{
    wheel_left.update();
    wheel_right.update();
    update_distance();

    if (show_info && info_period.isReady() ) {
        Serial.print("x:");
        Serial.print(giro_angles[0], 4);
        Serial.print(" y:");
        Serial.print(giro_angles[1], 4);
        Serial.print(" z:");
        Serial.print(giro_angles[2], 4);
        Serial.print(" d:");
        Serial.print(distance_cm);
        Serial.print(" l_s:");
        Serial.print(wheel_left.get_speed(), 4);
        Serial.print(" r_s:");
        Serial.print(wheel_right.get_speed(), 4);
        Serial.print("\n");
    }

    //потерянна связь с оператором.
    if(0)// (check_last_time && (micros() > last_cmd_time + 100000) )
    {
        //остановка машины.
        wheel_left.set_power(0.f);
        wheel_right.set_power(0.f);
        check_last_time = false;
    }
    //алгоритм обхода препятствий.
    else if ( enable_walk )
    {
        State::ProcessState res = cur_state->process();

        //cостояние не изменилось
        if (res == State::InProgress)
            return;
        
        //1. Двигали в перёд.        
        if (0)//(cur_state->get_type() == State::MoveForward )
        {
            //поворот на лево
            //Serial.println("start turn left");
            cur_state = turn_state;
            TurnState::Direction dir(TurnState::Left);
            cur_state->start(&dir);
        }
        //2. поворачивали.
        else if (cur_state->get_type() == State::Turn)
        {
            //Serial.println("turn before");

            //всё ок Двигаем дальше.
            if ( res == State::Ok )
            {
                //Serial.println("start move forward");
                cur_state = move_forward_state;
                cur_state->start(0);
            }
            //поворот не удался.
            else
            {
                //поверён на право
                if ( ((TurnState *)cur_state)->get_direction() == TurnState::Left )
                {
                    //Serial.println("start turn right");
                    cur_state = turn_state;
                    TurnState::Direction dir(TurnState::Right);
                    cur_state->start(&dir);
                }
                //отедим на зад.
                else
                {
                    //Serial.println("start move back");
                    cur_state = move_back_state;
                    cur_state->start(0);
                }
            }
        }
        //Двигали на задад
        else if (cur_state->get_type() == State::MoveBack)
        {
            //Serial.println("MoveBack before turn left");
            //поворачиваем на лево.
            cur_state = turn_state;

            TurnState::Direction dir(TurnState::Left);
            cur_state->start(&dir);
        }
        else if (cur_state->get_type() == State::TurnAngle)
        {
            cur_state = turn_angle_state;
            float angle(0.0);
            cur_state->start(&angle);
        }
    }
}

void Car::process_command(uint8_t * data, uint8_t data_size)
{
    if (data_size == 0)
        return;

    //левое колесо
    if ( data[0] == SetLeftWheelPower && data_size >= 5 )
    {
        wheel_left.set_power(*((float *)&data[1]));
        enable_walk = false;

        if (show_info) {
            Serial.print("left_power: ");
            Serial.print(*((float *)&data[1]));
            Serial.print("\n");
        }
    }
    //правое колесо
    else if ( data[0] == SetRightWheelPower  && data_size >= 5 )
    {
        wheel_right.set_power(*((float *)&data[1]));
        enable_walk = false;

        if (show_info) {
            Serial.print("right_power: ");
            Serial.print(*((float *)&data[1]));
            Serial.print("\n");
        }
    }
    //оба колеса.
    else if ( data[0] == SetWheelsPower  && data_size >= 9 )
    {
        float l = *((float *)&data[1]);
        float r = *((float *)&data[5]);
        wheel_left.set_power(l);
        wheel_right.set_power(r);
        enable_walk = false;
    }
    //остановка.
    else if ( data[0] == SetPowerZerro )
    {
        wheel_left.set_power(0.f);
        wheel_right.set_power(0.f);
        enable_walk = false;
    }
    else if ( data[0] == StartWalk )
    {
        start_walk();
    }
    else if ( data[0] == SetPidSettings )
    {
        struct Params{
          byte id;
          float p,i,d;
        } * params((Params *)&data[1]);

        Serial.print("SetPidSettings id:");
        Serial.print(params->id);
        Serial.print(" p:");
        Serial.print(params->p);
        Serial.print(" i:");
        Serial.print(params->i);
        Serial.print(" d:");
        Serial.print(params->d);
        Serial.print("\n");


        //установка пида угла
        if (params->id == 0){
            ((TurnAngleState *)turn_angle_state)->set_params(params->p, params->i, params->d);
        //установка пида левого колеса
        }else if (params->id == 1){
            wheel_left.pid.SetTunings(params->p, params->i, params->d);
            wheel_left.speed_control = true;
        //установка пида правого колеса
        }else if (params->id == 2){
            wheel_right.pid.SetTunings(params->p, params->i, params->d);
            wheel_right.speed_control = true;
        }
    }
    else if ( data[0] == SetAngle )
    {
        start_rotate(*((float *)&data[1]));
    }
    else if ( data[0] == SetPowerOffset ){
        ((TurnAngleState *)turn_angle_state)->set_offset(*((float *)&data[1]));
    }
    else if ( data[0] == EnableDebug ){
       show_info = (bool)data[1];
    }
    else if ( data[0] == SetWheelSpeed )
    {
        struct Params{
          byte id;
          long speed;
        } * params((Params *)&data[1]);

        Serial.print("SetWheelSpeed id:");
        Serial.print(params->id);
        Serial.print(" speed:");
        Serial.print(params->speed);
        Serial.print("\n");

        if (params->id == 0){
            wheel_left.set_abs_speed(params->speed);
            wheel_left.speed_control = true;
        //установка пида правого колеса
        }else if (params->id == 1){
            wheel_right.set_abs_speed(params->speed);
            wheel_right.speed_control = true;
        }
    }

    //Запрос времени комманды.
    if ( !enable_walk )
    {
        last_cmd_time = micros();
        check_last_time = true;
    }
}

void Car::start_walk()
{
    cur_state = move_forward_state;
    cur_state->start(0);
    enable_walk = true;
}

void Car::start_rotate(float angle)
{
    cur_state = turn_angle_state;
    cur_state->start(&angle);
    enable_walk = true;
}

void Car::update_distance()
{
    if ( micros() > ud_start_time + US_TRIGER_TIMEOUT_MK )
    {       
        distance_cm = ultrasonic.Ranging(CM);
        ud_start_time = micros();
     }
}
