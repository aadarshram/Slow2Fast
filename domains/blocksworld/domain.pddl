;; Four-operator blocksworld with a single gripper (STRIPS).
;; Same predicates and operators the learner was previously given as a hand-written Python dict.
(define (domain blocksworld)
  (:requirements :strips)
  (:predicates (on ?x ?y) (ontable ?x) (clear ?x) (handempty) (holding ?x))

  (:action pickup
    :parameters (?x)
    :precondition (and (clear ?x) (ontable ?x) (handempty))
    :effect (and (holding ?x) (not (clear ?x)) (not (ontable ?x)) (not (handempty))))

  (:action putdown
    :parameters (?x)
    :precondition (holding ?x)
    :effect (and (ontable ?x) (clear ?x) (handempty) (not (holding ?x))))

  (:action stack
    :parameters (?x ?y)
    :precondition (and (holding ?x) (clear ?y))
    :effect (and (on ?x ?y) (clear ?x) (handempty) (not (holding ?x)) (not (clear ?y))))

  (:action unstack
    :parameters (?x ?y)
    :precondition (and (on ?x ?y) (clear ?x) (handempty))
    :effect (and (holding ?x) (clear ?y) (not (on ?x ?y)) (not (clear ?x)) (not (handempty))))
)
