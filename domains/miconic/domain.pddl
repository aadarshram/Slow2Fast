;; Miconic (STRIPS): an elevator serves passengers. (above ?f1 ?f2): ?f2 is above ?f1.
(define (domain miconic)
  (:requirements :strips :typing)
  (:types passenger floor)
  (:predicates (origin ?p - passenger ?f - floor) (destin ?p - passenger ?f - floor)
               (above ?f1 - floor ?f2 - floor) (boarded ?p - passenger) (served ?p - passenger)
               (lift-at ?f - floor))
  (:action board
    :parameters (?f - floor ?p - passenger)
    :precondition (and (lift-at ?f) (origin ?p ?f))
    :effect (boarded ?p))
  (:action depart
    :parameters (?f - floor ?p - passenger)
    :precondition (and (lift-at ?f) (destin ?p ?f) (boarded ?p))
    :effect (and (not (boarded ?p)) (served ?p)))
  (:action up
    :parameters (?f1 - floor ?f2 - floor)
    :precondition (and (lift-at ?f1) (above ?f1 ?f2))
    :effect (and (lift-at ?f2) (not (lift-at ?f1))))
  (:action down
    :parameters (?f1 - floor ?f2 - floor)
    :precondition (and (lift-at ?f1) (above ?f2 ?f1))
    :effect (and (lift-at ?f2) (not (lift-at ?f1)))))
