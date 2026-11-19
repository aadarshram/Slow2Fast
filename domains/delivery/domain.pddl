;; Delivery: a robot with capacity one carries packages to their destinations on a grid of cells.
(define (domain delivery)
  (:requirements :strips :typing)
  (:types cell package)
  (:predicates (at-robot ?c - cell) (adjacent ?a - cell ?b - cell) (pkg-at ?p - package ?c - cell)
               (holding ?p - package) (hand-free))
  (:action move
    :parameters (?from - cell ?to - cell)
    :precondition (and (at-robot ?from) (adjacent ?from ?to))
    :effect (and (at-robot ?to) (not (at-robot ?from))))
  (:action pick
    :parameters (?p - package ?c - cell)
    :precondition (and (at-robot ?c) (pkg-at ?p ?c) (hand-free))
    :effect (and (holding ?p) (not (pkg-at ?p ?c)) (not (hand-free))))
  (:action drop
    :parameters (?p - package ?c - cell)
    :precondition (and (at-robot ?c) (holding ?p))
    :effect (and (pkg-at ?p ?c) (hand-free) (not (holding ?p)))))
