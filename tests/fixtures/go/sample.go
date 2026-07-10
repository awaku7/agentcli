package core

import (
	"context"
	"fmt"
)

// Person represents a person entity.
type Person struct {
	Name string
	Age  int
}

// NewPerson creates a new Person.
func NewPerson(name string, age int) *Person {
	return &Person{Name: name, Age: age}
}

// Greet returns a greeting string.
func (p *Person) Greet() string {
	return fmt.Sprintf("Hi, I'm %s", p.Name)
}

// Repository is a generic repository interface.
type Repository[T any] interface {
	GetByID(ctx context.Context, id int) (T, error)
	Save(ctx context.Context, entity T) error
}

// Status represents a status enum.
type Status int

const (
	StatusActive   Status = iota
	StatusInactive
	StatusPending
)

// Point is a 2D point.
type Point struct {
	X, Y int
}
