;; Ferry (classic): a ferry carries one car at a time between locations.
(define (domain ferry)
  (:requirements :strips :typing)
  (:types car location)
  (:predicates (at-ferry ?l - location) (at ?c - car ?l - location) (empty-ferry) (on ?c - car))
  (:action sail
    :parameters (?from - location ?to - location)
    :precondition (at-ferry ?from)
    :effect (and (at-ferry ?to) (not (at-ferry ?from))))
  (:action board
    :parameters (?c - car ?l - location)
    :precondition (and (at ?c ?l) (at-ferry ?l) (empty-ferry))
    :effect (and (on ?c) (not (at ?c ?l)) (not (empty-ferry))))
  (:action debark
    :parameters (?c - car ?l - location)
    :precondition (and (on ?c) (at-ferry ?l))
    :effect (and (at ?c ?l) (empty-ferry) (not (on ?c)))))
